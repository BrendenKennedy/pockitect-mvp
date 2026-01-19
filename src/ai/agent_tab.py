"""AI agent UI tab for natural language to YAML generation and command execution."""

from __future__ import annotations

import traceback
from pathlib import Path
import uuid
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QMessageBox,
    QScrollArea,
)

from .agent_service import AgentService, AgentResponse
from .preview_dialog import YAMLPreviewDialog
from .chat_widgets import MessageBubble, ToolCallBadge, TypingIndicator
from .yaml_summary import summarize_blueprint
from .model_selector import ModelSelectorWidget
from .models.factory import ModelFactory
from .models.config import get_model_config
from .privacy import DataAnonymizer
from app.core.config import PRIVACY_ENABLED
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
        self._session_id = uuid.uuid4().hex
        self._current_model_id = "pockitect-ai"  # Default model
        self._thread: Optional[QThread] = None
        self._worker: Optional[_AgentWorker] = None
        self._last_prompt: str = ""
        self._last_response: Optional[AgentResponse] = None
        self._last_blueprint = None
        self._last_errors: List[str] = []
        self._streaming_bubble: Optional[MessageBubble] = None
        self._streaming_text: str = ""
        self._tool_badges: List[ToolCallBadge] = []
        self._history_log: List[str] = []
        self._history_path = Path("data/cache/ai_history.txt")
        self._anonymizer: Optional[DataAnonymizer] = None
        self._setup_ui()
        self._update_agent_service()
        self._load_history()

    def _setup_ui(self):
        """Setup ChatGPT-style UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar: Model selector
        top_bar = QWidget()
        top_bar.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                border-bottom: 1px solid #0f3460;
            }
        """)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(16, 12, 16, 12)
        top_bar_layout.setSpacing(12)
        
        self.model_selector = ModelSelectorWidget()
        self.model_selector.model_changed.connect(self._on_model_changed)
        top_bar_layout.addWidget(self.model_selector)
        top_bar_layout.addStretch()
        
        self.new_session_btn = QPushButton("New Session")
        self.new_session_btn.clicked.connect(self._start_new_session)
        top_bar_layout.addWidget(self.new_session_btn)
        
        layout.addWidget(top_bar)

        # Chat area: Scrollable message list
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a2e;
                border: none;
            }
        """)

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background-color: #1a1a2e;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_layout.setSpacing(16)

        self._typing_indicator = TypingIndicator()
        self._typing_indicator.hide()

        self.chat_layout.addStretch(1)
        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)  # Stretch factor 1

        # Bottom: Input area
        input_container = QWidget()
        input_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                border-top: 1px solid #0f3460;
            }
        """)
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(16, 12, 16, 16)
        input_layout.setSpacing(8)

        # Action buttons row (hidden by default, shown when needed)
        self.action_buttons = QHBoxLayout()
        self.action_buttons.setSpacing(8)
        
        self.preview_btn = QPushButton("Preview / Save")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._show_preview_dialog)
        self.action_buttons.addWidget(self.preview_btn)

        self.confirm_btn = QPushButton("Confirm & Execute")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.confirm_btn.clicked.connect(self._on_confirm_execute)
        self.action_buttons.addWidget(self.confirm_btn)
        
        self.action_buttons.addStretch()
        self.action_buttons_widget = QWidget()
        self.action_buttons_widget.setLayout(self.action_buttons)
        self.action_buttons_widget.hide()
        input_layout.addWidget(self.action_buttons_widget)

        # Input field and send button
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        
        self.input_edit = _InputEdit(self._on_send_clicked, self)
        self.input_edit.setPlaceholderText(
            "Ask me to create infrastructure, deploy projects, start/stop instances, etc."
        )
        self.input_edit.setMinimumHeight(60)
        self.input_edit.setMaximumHeight(120)
        self.input_edit.setStyleSheet("""
            QTextEdit {
                background-color: #16213e;
                border: 1px solid #0f3460;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                color: #eaeaea;
            }
            QTextEdit:focus {
                border-color: #e94560;
            }
        """)
        input_row.addWidget(self.input_edit)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumWidth(80)
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #e94560;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
            QPushButton:disabled {
                background-color: #2a2a4a;
                color: #666;
            }
        """)
        self.send_btn.clicked.connect(self._on_send_clicked)
        input_row.addWidget(self.send_btn)
        
        input_layout.addLayout(input_row)
        layout.addWidget(input_container)

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
        self._tool_badges = []

        self._append_message("user", prompt)
        self._append_history_line(f"User: {prompt}")
        self._streaming_text = ""
        self._streaming_bubble = self._append_message("assistant", "")
        self._show_typing_indicator()

        # Clear input
        self.input_edit.clear()
        
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
        """Start a new chat session."""
        self.agent_service.session_manager.clear_session(self._session_id)
        self._session_id = uuid.uuid4().hex
        self._clear_messages()
        self._history_log = []
        self._save_history()
        if self._anonymizer:
            self._anonymizer.clear_mapping()
            self._anonymizer = None
        self._update_agent_service()
        
    def _on_model_changed(self, model_id: str):
        """Handle model selection change."""
        self._current_model_id = model_id
        self._update_agent_service()
        
    def _update_agent_service(self):
        """Update agent service with current model and privacy settings."""
        try:
            # Create new agent service with selected model
            self.agent_service = AgentService(
                monitor_tab=self.monitor_tab,
                model_id=self._current_model_id,
                session_id=self._session_id
            )
            
            # Connect signals
            self.agent_service.tool_started.connect(self._on_tool_started)
            self.agent_service.tool_finished.connect(self._on_tool_finished)
            self.agent_service.stream_chunk.connect(self._on_stream_chunk)
            
            # Privacy anonymizer is now handled by AgentService
            self._anonymizer = self.agent_service.anonymizer
                
        except Exception as e:
            logger.exception(f"Failed to update agent service: {e}")
            QMessageBox.warning(self, "Model Error", f"Failed to initialize model: {e}")

    def _on_response_received(self, response: AgentResponse):
        """Handle response from agent service."""
        self._last_response = response
        self._set_loading_state(False)
        self._hide_typing_indicator()

        if not self._streaming_bubble:
            self._streaming_bubble = self._append_message("assistant", "")

        # Handle different response types
        if response.intent.type == "create" and response.blueprint:
            # YAML generation
            from .validator import BlueprintValidator
            validator = BlueprintValidator()
            valid, errors = validator.validate(response.blueprint)
            self._last_blueprint = response.blueprint
            self._last_errors = [] if valid else errors

            summary = summarize_blueprint(response.blueprint)
            self._streaming_bubble.set_text(summary)
            self._append_history_line(f"Assistant: {summary}")
            self.preview_btn.setEnabled(True)
            self.action_buttons_widget.show()
            self.confirm_btn.setEnabled(False)
        
        elif response.requires_confirmation:
            # Command requiring confirmation
            self._streaming_bubble.set_text(response.message)
            self._append_history_line(f"Assistant: {response.message}")
            self.preview_btn.setEnabled(False)
            self.confirm_btn.setEnabled(True)
            self.action_buttons_widget.show()
        
        else:
            # Query or other non-action response
            final_text = response.message if response.message else self._streaming_text
            self._streaming_bubble.set_text(final_text)
            self._append_history_line(f"Assistant: {final_text}")
            self.preview_btn.setEnabled(False)
            self.confirm_btn.setEnabled(False)
            self.action_buttons_widget.hide()
        
        self._save_history()

    def _on_request_failed(self, message: str):
        """Handle request failure."""
        self._set_loading_state(False)
        self._hide_typing_indicator()
        error_msg = f"❌ Request failed: {message}"
        self._append_message("assistant", error_msg)
        self._append_history_line(f"User: {self._last_prompt}")
        self._append_history_line(f"Assistant: {error_msg}")
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
                self._append_history_line(f"Deployment started: {project_name}")
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
                self._append_history_line(f"{action.capitalize()} command: {project_name}")
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
                    self._append_history_line(f"Terminated: {project_name}")
            
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
            self._append_history_line(f"Scan requested: {region or 'all regions'}")
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

    def _append_message(self, role: str, text: str) -> MessageBubble:
        """Append a message bubble to the chat."""
        bubble = MessageBubble(text, role=role)
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        if role == "user":
            # User messages: right-aligned
            layout.addStretch(2)
            layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
            layout.addStretch(1)
        else:
            # Assistant messages: left-aligned
            layout.addStretch(1)
            layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            layout.addStretch(2)

        # Insert before the stretch at the end
        insert_index = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(insert_index, wrapper)
        self._scroll_to_bottom()
        return bubble

    def _append_history_line(self, line: str) -> None:
        self._history_log.append(line)

    def _clear_messages(self) -> None:
        while self.chat_layout.count() > 2:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._streaming_bubble = None
        self._streaming_text = ""

    def _scroll_to_bottom(self) -> None:
        bar = self.chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _show_typing_indicator(self) -> None:
        self._typing_indicator.show()
        self._typing_indicator.start()
        self._scroll_to_bottom()

    def _hide_typing_indicator(self) -> None:
        self._typing_indicator.stop()
        self._typing_indicator.hide()

    def _on_tool_started(self, tool_name: str) -> None:
        """Handle tool call started."""
        badge = ToolCallBadge(tool_name, status="running")
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

        insert_index = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(insert_index, wrapper)
        self._tool_badges.append(badge)
        self._scroll_to_bottom()

    def _on_tool_finished(self, tool_name: str, result: str) -> None:
        """Handle tool call finished."""
        for badge in reversed(self._tool_badges):
            label = badge.findChild(QLabel)
            if label and tool_name in label.text():
                badge.update_status(tool_name, status="done")
                break
        # Don't show tool results as separate messages - they're part of the context

    def _on_stream_chunk(self, text: str) -> None:
        if not text:
            return
        if not self._streaming_bubble:
            self._streaming_bubble = self._append_message("assistant", "")
        self._streaming_text += text
        self._streaming_bubble.set_text(self._streaming_text)
        self._scroll_to_bottom()

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
        """Update UI state during loading."""
        self.send_btn.setEnabled(not loading)
        self.input_edit.setEnabled(not loading)
        if not loading:
            self.preview_btn.setEnabled(bool(self._last_blueprint))
        else:
            self.preview_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)  # Will be enabled by response handler if needed

    def _load_history(self):
        if not self._history_path.exists():
            return
        try:
            content = self._history_path.read_text(encoding="utf-8")
            if content.strip():
                self._history_log = content.splitlines()
                self._append_message("assistant", f"Previous session:\n{content}")
        except Exception:
            logger.debug("Failed to load AI history.")

    def _save_history(self):
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._history_path.write_text("\n".join(self._history_log), encoding="utf-8")
        except Exception:
            logger.debug("Failed to save AI history.")
