"""AI agent UI tab for natural language to YAML generation and command execution."""

from __future__ import annotations

import traceback
from pathlib import Path
import uuid
from typing import List, Optional

import yaml
from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QMessageBox,
)

from .agent_service import AgentService, AgentResponse
from .preview_dialog import YAMLPreviewDialog
import logging

logger = logging.getLogger(__name__)


class _InputEdit(QTextEdit):
    def __init__(self, on_send, parent=None):
        super().__init__(parent)
        self._on_send = on_send

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers():
                super().keyPressEvent(event)
                return
            self._on_send()
            return
        super().keyPressEvent(event)


class _AgentWorker(QObject):
    finished = Signal(object)  # AgentResponse
    failed = Signal(str)

    def __init__(self, user_input: str, agent_service: AgentService, session_id: str):
        super().__init__()
        self.user_input = user_input
        self.agent_service = agent_service
        self.session_id = session_id

    def run(self):
        try:
            response = self.agent_service.process_request(self.user_input, session_id=self.session_id)
            self.finished.emit(response)
        except Exception as exc:
            message = f"{exc}\n{traceback.format_exc(limit=2)}"
            self.failed.emit(message)


class AIAgentTab(QWidget):
    def __init__(self, monitor_tab=None, parent=None):
        super().__init__(parent)
        self.monitor_tab = monitor_tab
        self.agent_service = AgentService(monitor_tab=monitor_tab)
        self._thread: Optional[QThread] = None
        self._worker: Optional[_AgentWorker] = None
        self._session_id = uuid.uuid4().hex
        self._last_prompt: str = ""
        self._last_response: Optional[AgentResponse] = None
        self._last_blueprint = None
        self._last_errors: List[str] = []
        self._history_path = Path("data/cache/ai_history.txt")
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("AI Assistant (Ollama)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

        self.input_edit = _InputEdit(self._on_send_clicked, self)
        self.input_edit.setPlaceholderText(
            "Ask me to create infrastructure, deploy projects, start/stop instances, etc.\n"
            "Examples:\n"
            "- Create a t3.micro Ubuntu web server in us-east-1\n"
            "- Deploy the blog-backend project\n"
            "- Stop my web-server project\n"
            "- List all my projects"
        )
        self.input_edit.setMinimumHeight(90)
        layout.addWidget(self.input_edit)

        button_row = QHBoxLayout()
        self.generate_btn = QPushButton("Send")
        self.generate_btn.clicked.connect(self._on_send_clicked)
        button_row.addWidget(self.generate_btn)

        self.new_session_btn = QPushButton("New Session")
        self.new_session_btn.clicked.connect(self._start_new_session)
        button_row.addWidget(self.new_session_btn)

        self.preview_btn = QPushButton("Preview / Save")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._show_preview_dialog)
        button_row.addWidget(self.preview_btn)

        self.confirm_btn = QPushButton("Confirm & Execute")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.confirm_btn.clicked.connect(self._on_confirm_execute)
        button_row.addWidget(self.confirm_btn)

        button_row.addStretch()
        layout.addLayout(button_row)

        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setPlaceholderText("Conversation history will appear here.")
        self.history_text.setMinimumHeight(120)
        layout.addWidget(self.history_text)

        self.yaml_preview = QTextEdit()
        self.yaml_preview.setReadOnly(True)
        self.yaml_preview.setPlaceholderText("Generated YAML will appear here.")
        self.yaml_preview.setMinimumHeight(180)
        layout.addWidget(self.yaml_preview)

    def _on_send_clicked(self):
        prompt = self.input_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Missing Input", "Please enter a request.")
            return
        self._start_processing(prompt)

    def _start_processing(self, prompt: str):
        if self._thread and self._thread.isRunning():
            QMessageBox.information(self, "Working", "A request is already in progress.")
            return

        self._last_prompt = prompt
        self._set_loading_state(True)

        self._thread = QThread(self)
        self._worker = _AgentWorker(prompt, self.agent_service, self._session_id)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_response_received)
        self._worker.failed.connect(self._on_request_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)

        self._thread.start()

    def _start_new_session(self):
        self.agent_service.session_manager.clear_session(self._session_id)
        self._session_id = uuid.uuid4().hex
        self.history_text.clear()
        self._save_history()
        self.status_label.setText("New session started.")

    def _on_response_received(self, response: AgentResponse):
        self._last_response = response
        self._set_loading_state(False)

        # Update history
        self.history_text.append(f"User: {self._last_prompt}")
        self.history_text.append(f"Assistant: {response.message}")
        self.history_text.append("")
        self._save_history()

        # Handle different response types
        if response.intent.type == "create" and response.blueprint:
            # YAML generation
            from .validator import BlueprintValidator
            validator = BlueprintValidator()
            valid, errors = validator.validate(response.blueprint)
            self._last_blueprint = response.blueprint
            self._last_errors = [] if valid else errors

            yaml_text = yaml.safe_dump(response.blueprint, sort_keys=False)
            self.yaml_preview.setText(yaml_text)
            self.preview_btn.setEnabled(True)
            self.confirm_btn.setEnabled(False)

            if errors:
                self.status_label.setText(f"Generated with {len(errors)} validation issue(s).")
            else:
                self.status_label.setText("YAML generated successfully.")
        
        elif response.requires_confirmation:
            # Command requiring confirmation
            self.yaml_preview.setText(f"Command: {response.intent.type}\n\n{response.message}")
            self.preview_btn.setEnabled(False)
            self.confirm_btn.setEnabled(True)
            self.status_label.setText("Action ready. Confirm to execute.")
        
        else:
            # Query or other non-action response
            self.yaml_preview.setText(response.message)
            self.preview_btn.setEnabled(False)
            self.confirm_btn.setEnabled(False)
            self.status_label.setText("Response received.")

    def _on_request_failed(self, message: str):
        self._set_loading_state(False)
        self.status_label.setText("Request failed.")
        self.history_text.append(f"User: {self._last_prompt}")
        self.history_text.append("Assistant: Request failed. See error dialog for details.")
        self.history_text.append("")
        self._save_history()
        QMessageBox.critical(self, "Error", message)

    def _on_confirm_execute(self):
        """Execute a confirmed command."""
        if not self._last_response or not self._last_response.requires_confirmation:
            return
        
        details = self._last_response.confirmation_details
        if not details:
            return
        
        intent = self._last_response.intent
        
        # Show confirmation dialog for destructive actions
        if intent.type in ("terminate", "power") and intent.type == "terminate":
            reply = QMessageBox.question(
                self,
                "Confirm Termination",
                f"Are you sure you want to terminate resources for '{details.get('project_name', 'unknown')}'?\n\n"
                "This action cannot be undone and will delete AWS resources.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Execute the command
        try:
            if intent.type == "deploy":
                self._execute_deploy(details.get("project_name"))
            elif intent.type == "power":
                self._execute_power(details.get("project_name"), details.get("action"))
            elif intent.type == "terminate":
                self._execute_terminate(details.get("project_name"), details.get("region"))
            elif intent.type == "scan":
                self._execute_scan(details.get("region"))
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Failed to execute command: {str(e)}")
            logger.exception("Command execution failed")

    def _execute_deploy(self, project_name: str):
        """Execute deploy command."""
        from deploy_worker import ProjectDeployWorker
        from storage import load_project, slugify
        
        slug = slugify(project_name)
        blueprint = load_project(slug)
        if not blueprint:
            QMessageBox.warning(self, "Not Found", f"Project '{project_name}' not found.")
            return
        
        worker = ProjectDeployWorker(blueprint, parent=self)
        
        def on_finished(success: bool, message: str):
            if success:
                self.status_label.setText(f"Deployment started for '{project_name}'.")
                self.history_text.append(f"Deployment started: {project_name}")
            else:
                self.status_label.setText(f"Deployment failed: {message}")
                QMessageBox.warning(self, "Deployment Failed", message)
        
        worker.finished.connect(on_finished)
        worker.start()
        self.confirm_btn.setEnabled(False)

    def _execute_power(self, project_name: str, action: str):
        """Execute power command (start/stop)."""
        from workers import PowerWorker
        
        monitor_resources = self.monitor_tab.resources if self.monitor_tab else None
        worker = PowerWorker(project_name, action, parent=self, monitor_resources=monitor_resources)
        
        def on_finished(success: bool, message: str):
            if success:
                self.status_label.setText(f"{action.capitalize()} command sent for '{project_name}'.")
                self.history_text.append(f"{action.capitalize()} command: {project_name}")
            else:
                self.status_label.setText(f"Power action failed: {message}")
                QMessageBox.warning(self, "Power Action Failed", message)
        
        worker.finished.connect(on_finished)
        worker.start()
        self.confirm_btn.setEnabled(False)

    def _execute_terminate(self, project_name: Optional[str], region: Optional[str]):
        """Execute terminate command."""
        if project_name:
            from workers import DeleteWorker
            from app.core.aws.resource_tracker import ResourceTracker
            
            # Get resources for project
            tracker = ResourceTracker()
            all_resources = []
            for res_type in ["ec2_instance", "rds_instance", "s3_bucket"]:
                res_list = tracker.get_active_resources(project=project_name, resource_type=res_type)
                all_resources.extend(res_list)
            
            if not all_resources:
                QMessageBox.warning(self, "No Resources", f"No resources found for project '{project_name}'.")
                return
            
            # Convert to ScannedResource format
            from app.core.aws.scanner import ScannedResource
            resources = [
                ScannedResource(
                    id=r.resource_id,
                    type=r.resource_type,
                    region=r.region,
                    name="",
                    state="",
                    tags={"pockitect:project": project_name},
                    details={}
                )
                for r in all_resources
            ]
            
            worker = DeleteWorker(resources, parent=self, project_name=project_name)
            
            def on_finished(success_ids: list, errors: list):
                if errors:
                    self.status_label.setText(f"Termination completed with {len(errors)} errors.")
                    QMessageBox.warning(self, "Termination Errors", f"Some resources failed:\n{chr(10).join(errors[:5])}")
                else:
                    self.status_label.setText(f"Termination completed for '{project_name}'.")
                    self.history_text.append(f"Terminated: {project_name}")
            
            worker.finished.connect(on_finished)
            worker.start()
        elif region:
            # Region-based termination would need different implementation
            QMessageBox.information(self, "Not Implemented", "Region-based termination not yet implemented.")
        
        self.confirm_btn.setEnabled(False)

    def _execute_scan(self, region: Optional[str]):
        """Execute scan command."""
        if self.monitor_tab and hasattr(self.monitor_tab, 'monitor_service'):
            self.monitor_tab.monitor_service.request_scan(regions=[region] if region else None)
            self.status_label.setText(f"Scan requested for {region or 'all regions'}.")
            self.history_text.append(f"Scan requested: {region or 'all regions'}")
        else:
            QMessageBox.warning(self, "Not Available", "Monitor service not available.")
        
        self.confirm_btn.setEnabled(False)

    def _cleanup_worker(self):
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None

    def _show_preview_dialog(self):
        if not self._last_blueprint:
            return
        dialog = YAMLPreviewDialog(
            blueprint=self._last_blueprint,
            errors=self._last_errors,
            parent=self,
        )
        dialog.regenerate_requested.connect(self._regenerate_from_dialog)
        dialog.exec()

    def _regenerate_from_dialog(self):
        if self._last_prompt:
            self._start_processing(self._last_prompt)

    def _set_loading_state(self, loading: bool):
        self.generate_btn.setEnabled(not loading)
        self.input_edit.setEnabled(not loading)
        self.preview_btn.setEnabled(not loading and bool(self._last_blueprint))
        self.confirm_btn.setEnabled(False)  # Will be enabled by response handler if needed
        if loading:
            self.status_label.setText("Processing...")

    def _load_history(self):
        if not self._history_path.exists():
            return
        try:
            content = self._history_path.read_text(encoding="utf-8")
            if content.strip():
                self.history_text.setText(content)
        except Exception:
            logger.debug("Failed to load AI history.")

    def _save_history(self):
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._history_path.write_text(self.history_text.toPlainText(), encoding="utf-8")
        except Exception:
            logger.debug("Failed to save AI history.")
