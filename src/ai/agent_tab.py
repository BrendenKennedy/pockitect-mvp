"""AI agent UI tab for natural language to YAML generation and command execution."""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import uuid

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
    QListWidget,
    QListWidgetItem,
    QToolButton,
)

from .agent_service import AgentService, AgentResponse
from .preview_dialog import YAMLPreviewDialog
from .chat_widgets import MessageBubble, ToolCallBadge
from .yaml_summary import summarize_blueprint
from .model_selector import ModelSelectorWidget
from .models.factory import ModelFactory
from .models.config import get_model_config
from .privacy import DataAnonymizer
from app.core.config import PRIVACY_ENABLED
from storage import get_preference
from styles import ThemeManager

logger = logging.getLogger(__name__)


def _get_theme_colors() -> dict[str, str]:
    theme_name = get_preference("theme", "modern_dark")
    return ThemeManager.get_colors(theme_name)


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
        self._colors = _get_theme_colors()
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
        self._generation_badge: Optional[ToolCallBadge] = None
        self._generation_badge_should_show: bool = False
        self._session_messages: List[dict] = []
        self._session_meta: dict = {}
        self._sessions_dir = Path("data/cache/ai_sessions")
        self._anonymizer: Optional[DataAnonymizer] = None
        self._setup_ui()
        self._update_agent_service()
        self._load_sessions()

    def _setup_ui(self):
        """Setup ChatGPT-style UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar: sidebar toggle
        top_bar = QWidget()
        # Styling handled by global theme
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(16, 12, 16, 12)
        top_bar_layout.setSpacing(12)

        self._sidebar_collapsed = False
        self.sidebar_toggle_btn = QToolButton()
        self.sidebar_toggle_btn.setText("Hide Chats")
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        top_bar_layout.addWidget(self.sidebar_toggle_btn)

        top_bar_layout.addStretch()
        
        layout.addWidget(top_bar)

        # Content row: session list + chat
        content_row = QHBoxLayout()

        sidebar = QWidget()
        sidebar.setMaximumWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        sidebar_label = QLabel("Chats")
        sidebar_label.setStyleSheet(
            f"color: {self._colors['text_primary']}; font-weight: bold;"
        )
        sidebar_layout.addWidget(sidebar_label)

        self.sessions_list = QListWidget()
        self.sessions_list.itemClicked.connect(self._on_session_selected)
        sidebar_layout.addWidget(self.sessions_list, 1)

        self.sidebar = sidebar
        content_row.addWidget(sidebar, 0)

        # Chat area: Scrollable message list
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Styling handled by global theme
        self.chat_container = QWidget()
        # Styling handled by global theme
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_layout.setSpacing(16)

        self.chat_layout.addStretch(1)
        self.chat_scroll.setWidget(self.chat_container)
        content_row.addWidget(self.chat_scroll, 1)

        layout.addLayout(content_row, 1)

        # Bottom: Input area
        input_container = QWidget()
        input_container.setStyleSheet(
            f"""
            QWidget {{
                background-color: {self._colors['bg_primary']};
                border-top: 1px solid {self._colors['border_primary']};
            }}
            """
        )
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
        self.confirm_btn.setStyleSheet(
            f"background-color: {self._colors['status_ok']}; color: {self._colors['text_primary']}; font-weight: bold;"
        )
        self.confirm_btn.clicked.connect(self._on_confirm_execute)
        self.action_buttons.addWidget(self.confirm_btn)
        
        self.action_buttons.addStretch()
        self.action_buttons_widget = QWidget()
        self.action_buttons_widget.setLayout(self.action_buttons)
        self.action_buttons_widget.hide()
        input_layout.addWidget(self.action_buttons_widget)

        # Input field and send button (chat bar)
        chat_bar = QWidget()
        chat_bar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {self._colors['bg_secondary']};
                border: 1px solid {self._colors['border_primary']};
                border-radius: 8px;
            }}
            """
        )
        chat_bar_layout = QHBoxLayout(chat_bar)
        chat_bar_layout.setContentsMargins(8, 6, 8, 6)
        chat_bar_layout.setSpacing(8)

        self.new_chat_btn = QPushButton("New Chat")
        self.new_chat_btn.setMinimumHeight(28)
        self.new_chat_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self._colors['bg_tertiary']};
                color: {self._colors['text_primary']};
                border: none;
                border-radius: 8px;
                font-weight: 600;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {self._colors['bg_hover']};
            }}
            """
        )
        self.new_chat_btn.clicked.connect(self._start_new_session)
        chat_bar_layout.addWidget(self.new_chat_btn)
        self._update_chat_bar_controls()

        self.input_edit = _InputEdit(self._on_send_clicked, self)
        self.input_edit.setPlaceholderText(
            "Ask me to create infrastructure, deploy projects, start/stop instances, etc."
        )
        self.input_edit.setFixedHeight(28)  # Single row height inside chat bar
        self.input_edit.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                padding: 6px 4px;
                font-size: 14px;
                color: {self._colors['text_primary']};
            }}
            """
        )
        chat_bar_layout.addWidget(self.input_edit, 1)

        # Model selector in chat bar (right side)
        self.model_selector = ModelSelectorWidget(show_settings_button=False, compact=True)
        self.model_selector.model_changed.connect(self._on_model_changed)
        # Hide label and status for compact display
        self.model_selector.status_label.hide()
        for i in range(self.model_selector.layout().count()):
            item = self.model_selector.layout().itemAt(i)
            if item:
                widget = item.widget()
                if isinstance(widget, QLabel) and widget.text() == "Model:":
                    widget.hide()
                    break
        chat_bar_layout.addWidget(self.model_selector)

        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumWidth(80)
        self.send_btn.setMinimumHeight(32)
        self.send_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self._colors['accent']};
                color: {self._colors['text_primary']};
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {self._colors['bg_disabled']};
                color: {self._colors['text_disabled']};
            }}
            """
        )
        self.send_btn.clicked.connect(self._on_send_clicked)
        chat_bar_layout.addWidget(self.send_btn)

        input_layout.addWidget(chat_bar)
        layout.addWidget(input_container)

    def _on_send_clicked(self):
        prompt = self.input_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Missing Input", "Please enter a request.")
            return
        if self._handle_confirmation_reply(prompt):
            return
        prompt = self._rewrite_choice_prompt(prompt)
        self._start_processing(prompt)

    def _handle_confirmation_reply(self, prompt: str) -> bool:
        if not self._last_response or not self._last_response.requires_confirmation:
            return False

        if self._is_affirmative(prompt):
            self._append_message("user", prompt)
            self._record_message("user", prompt)
            self._append_message("assistant", "Confirmed. Executing now.")
            self._record_message("assistant", "Confirmed. Executing now.")
            self.input_edit.clear()
            self._on_confirm_execute()
            return True

        return False

    def _is_affirmative(self, prompt: str) -> bool:
        normalized = prompt.strip().lower()
        if not normalized:
            return False
        confirmations = {
            "ok",
            "okay",
            "yes",
            "y",
            "yep",
            "yeah",
            "sure",
            "do it",
            "go ahead",
            "confirm",
            "sounds good",
        }
        if normalized in confirmations:
            return True
        for phrase in confirmations:
            if normalized.startswith(phrase + " "):
                return True
        return False

    def _rewrite_choice_prompt(self, prompt: str) -> str:
        if not self._last_response or not self._last_response.message:
            return prompt

        stripped = prompt.strip()
        if not stripped.isdigit():
            return prompt

        choice = int(stripped)
        if choice < 1 or choice > 5:
            return prompt

        last_message = self._last_response.message.strip()
        if not last_message:
            return prompt

        return (
            f"User selected option {choice} from the previous assistant message.\n\n"
            f"Previous assistant message:\n{last_message}\n\n"
            "Proceed with that selection."
        )

    def _start_processing(self, prompt: str):
        if self._thread and self._thread.isRunning():
            QMessageBox.information(self, "Working", "A request is already in progress.")
            return

        self._last_prompt = prompt
        self._set_loading_state(True)
        self._tool_badges = []

        self._append_message("user", prompt)
        self._record_message("user", prompt)
        # Clear streaming state and create new bubble for streaming
        self._streaming_text = ""
        self._streaming_bubble = self._append_message("assistant", "")
        # Don't show generation badge yet - wait to see if scan is needed first
        # (scan badge will replace it if scan is triggered)
        self._generation_badge_should_show = True
        self._scroll_to_bottom(force=True)

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
        self._clear_messages()
        self._create_session()
        self.agent_service.session_manager.clear_session(self._session_id)
        self.sessions_list.setCurrentRow(0)
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
        self._hide_generation_badge()

        if not self._streaming_bubble:
            self._streaming_bubble = self._append_message("assistant", "")

        # Handle different response types
        if response.intent.type == "create" and response.blueprint:
            # YAML generation - show the actual streamed YAML text, not a summary
            from .validator import BlueprintValidator
            validator = BlueprintValidator()
            valid, errors = validator.validate(response.blueprint)
            self._last_blueprint = response.blueprint
            self._last_errors = [] if valid else errors

            # Keep the streamed text (actual YAML) if available, otherwise show summary
            if self._streaming_text and self._streaming_text.strip():
                final_text = self._streaming_text
            else:
                final_text = summarize_blueprint(response.blueprint)
            self._streaming_bubble.set_text(final_text)
            self._record_message("assistant", final_text)
            self.preview_btn.setEnabled(True)
            self.action_buttons_widget.show()
            self.confirm_btn.setEnabled(False)
        
        elif response.requires_confirmation:
            # Command requiring confirmation
            self._streaming_bubble.set_text(response.message)
            self._record_message("assistant", response.message)
            self.preview_btn.setEnabled(False)
            self.confirm_btn.setEnabled(True)
            self.action_buttons_widget.show()
        
        else:
            # Query or other non-action response
            final_text = response.message if response.message else self._streaming_text
            self._streaming_bubble.set_text(final_text)
            self._record_message("assistant", final_text)
            self.preview_btn.setEnabled(False)
            self.confirm_btn.setEnabled(False)
            self.action_buttons_widget.hide()
        
        self._save_session()

    def _on_request_failed(self, message: str):
        """Handle request failure."""
        self._set_loading_state(False)
        self._hide_generation_badge()
        error_msg = f"❌ Request failed: {message}"
        self._append_message("assistant", error_msg)
        self._record_message("user", self._last_prompt)
        self._record_message("assistant", error_msg)
        self._save_session()
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
                self._record_message("assistant", f"Deployment started: {project_name}")
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
                self._record_message("assistant", f"{action.capitalize()} command: {project_name}")
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
                    self._record_message("assistant", f"Terminated: {project_name}")
            
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
            self._record_message("assistant", f"Scan requested: {region or 'all regions'}")
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
            # User messages: fully right-aligned
            layout.addStretch(10)
            layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
            layout.addStretch(0)
        else:
            # Assistant messages: fully left-aligned
            layout.addStretch(0)
            layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            layout.addStretch(10)

        # Insert before the stretch at the end
        insert_index = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(insert_index, wrapper)
        self._scroll_to_bottom()
        return bubble

    def _record_message(self, role: str, text: str) -> None:
        payload = {
            "role": role,
            "text": text,
            "timestamp": self._now(),
        }
        self._session_messages.append(payload)
        if role == "user" and self._session_meta.get("title") == "New chat":
            self._session_meta["title"] = text.strip()[:60] or "New chat"
        self._save_session()
        self._refresh_sessions_list()

    def _clear_messages(self) -> None:
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._streaming_bubble = None
        self._streaming_text = ""

    def _scroll_to_bottom(self, force: bool = False) -> None:
        bar = self.chat_scroll.verticalScrollBar()
        if force or self._should_autoscroll(bar):
            bar.setValue(bar.maximum())

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        if self._sidebar_collapsed:
            self.sidebar.setVisible(False)
            self.sidebar_toggle_btn.setText("Show Chats")
        else:
            self.sidebar.setVisible(True)
            self.sidebar_toggle_btn.setText("Hide Chats")
        self._update_chat_bar_controls()

    def _update_chat_bar_controls(self) -> None:
        if hasattr(self, "new_chat_btn"):
            self.new_chat_btn.setVisible(not self._sidebar_collapsed)

    @staticmethod
    def _should_autoscroll(bar) -> bool:
        threshold = 40
        return bar.value() >= (bar.maximum() - threshold)

    def _on_tool_started(self, tool_name: str) -> None:
        """Handle tool call started."""
        # For scan_resources, replace generation badge with scan badge
        if tool_name == "scan_resources":
            # Hide generation badge if shown, and don't show it after scan
            if self._generation_badge:
                self._generation_badge.hide()
                self._generation_badge = None
            self._generation_badge_should_show = False  # Don't show gen badge until scan done
            badge_text = "Scanning AWS resources..."
        else:
            badge_text = tool_name
        
        badge = ToolCallBadge(badge_text, status="running")
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

    def _show_generation_badge(self) -> None:
        if self._generation_badge:
            return
        if not self._generation_badge_should_show:
            return  # Don't show if scan is in progress
        badge = ToolCallBadge("Generating response", status="running")
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

        insert_index = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(insert_index, wrapper)
        self._generation_badge = badge
        self._scroll_to_bottom()

    def _hide_generation_badge(self) -> None:
        if not self._generation_badge:
            return
        self._generation_badge.update_status("Generating response", status="done")
        self._generation_badge = None

    def _on_tool_finished(self, tool_name: str, result: str) -> None:
        """Handle tool call finished."""
        for badge in reversed(self._tool_badges):
            label = badge.findChild(QLabel)
            if label:
                # Match by tool name or scan text
                badge_text = label.text()
                if tool_name in badge_text or (tool_name == "scan_resources" and "scan" in badge_text.lower()):
                    badge.update_status(badge_text, status="done")
                    # For scan completion, show a message and show generation badge
                    if tool_name == "scan_resources":
                        if "completed successfully" in result.lower() or "completed" in result.lower():
                            self._append_message("assistant", "✅ Scan complete. Using updated resource data.")
                        # Now show generation badge after scan is done
                        self._generation_badge_should_show = True
                        if not self._generation_badge:
                            self._show_generation_badge()
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

    def _load_sessions(self):
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._refresh_sessions_list()
        if self.sessions_list.count() > 0:
            self.sessions_list.setCurrentRow(0)
            item = self.sessions_list.item(0)
            if item:
                self._load_session(item.data(Qt.UserRole))
        else:
            self._start_new_session()

    def _refresh_sessions_list(self):
        sessions = []
        for path in self._sessions_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                sessions.append(payload.get("meta", {}))
            except Exception:
                continue

        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        self.sessions_list.clear()
        current_row = None
        for idx, meta in enumerate(sessions):
            title = meta.get("title") or "New chat"
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, meta.get("id"))
            self.sessions_list.addItem(item)
            if meta.get("id") == self._session_id:
                current_row = idx
        if current_row is not None:
            self.sessions_list.setCurrentRow(current_row)

    def _create_session(self) -> None:
        self._session_id = uuid.uuid4().hex
        now = self._now()
        self._session_meta = {
            "id": self._session_id,
            "title": "New chat",
            "created_at": now,
            "updated_at": now,
        }
        self._session_messages = []
        self._save_session()
        self._refresh_sessions_list()

    def _load_session(self, session_id: str) -> None:
        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._session_id = session_id
        self._session_meta = payload.get("meta", {})
        self._session_messages = payload.get("messages", [])
        self._last_response = None
        self._last_blueprint = None
        self._last_errors = []
        self._streaming_text = ""
        self._streaming_bubble = None
        self.agent_service.session_manager.clear_session(self._session_id)
        self._rehydrate_session_manager()
        self._render_messages()

    def _save_session(self) -> None:
        if not self._session_id:
            return
        self._session_meta["updated_at"] = self._now()
        payload = {
            "meta": self._session_meta,
            "messages": self._session_messages,
        }
        path = self._sessions_dir / f"{self._session_id}.json"
        try:
            self._sessions_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Failed to save chat session.")

    def _render_messages(self) -> None:
        self._clear_messages()
        for message in self._session_messages:
            role = message.get("role") or "assistant"
            text = message.get("text") or ""
            if text:
                self._append_message(role, text)

    def _rehydrate_session_manager(self) -> None:
        pending_user = None
        for message in self._session_messages:
            role = message.get("role")
            text = message.get("text") or ""
            if role == "user":
                pending_user = text
            elif role == "assistant" and pending_user:
                self.agent_service.session_manager.append_turn(
                    self._session_id, pending_user, text, None
                )
                pending_user = None

    def _on_session_selected(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.UserRole)
        if session_id and session_id != self._session_id:
            self._load_session(session_id)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
