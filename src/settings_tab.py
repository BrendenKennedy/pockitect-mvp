from typing import Callable
import keyring
import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QLineEdit,
    QFormLayout,
    QMessageBox,
)

from ai.model_selector import APIKeyDialog

logger = logging.getLogger(__name__)
KEYRING_SERVICE = "PockitectApp"


class SettingsTab(QWidget):
    def __init__(self, run_vpc_check: Callable[[], None], parent=None):
        super().__init__(parent)
        self._run_vpc_check = run_vpc_check
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        vpc_group = QGroupBox("Configure VPCs")
        vpc_layout = QVBoxLayout(vpc_group)
        vpc_layout.addWidget(
            QLabel(
                "Run a managed VPC check to associate existing VPCs "
                "or create missing ones."
            )
        )
        run_button = QPushButton("Run Managed VPC Check")
        run_button.clicked.connect(self._run_vpc_check)
        vpc_layout.addWidget(run_button)
        layout.addWidget(vpc_group)

        # AI Models API Keys
        ai_group = QGroupBox("AI Model API Keys")
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.addWidget(
            QLabel(
                "Configure API keys for cloud AI models (GPT, Claude).\n"
                "Keys are stored securely using your system keyring."
            )
        )
        
        ai_form = QFormLayout()
        
        # OpenAI API Key
        openai_row = QHBoxLayout()
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setPlaceholderText("sk-...")
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        openai_key = keyring.get_password(KEYRING_SERVICE, "openai_api_key")
        if openai_key:
            self.openai_key_edit.setText(openai_key)
            self.openai_key_edit.setPlaceholderText("(Enter new key to update)")
        openai_row.addWidget(self.openai_key_edit)
        
        openai_save_btn = QPushButton("Save")
        openai_save_btn.clicked.connect(lambda: self._save_api_key("openai_api_key", self.openai_key_edit.text()))
        openai_row.addWidget(openai_save_btn)
        ai_form.addRow("OpenAI API Key:", openai_row)
        
        # Anthropic API Key
        anthropic_row = QHBoxLayout()
        self.anthropic_key_edit = QLineEdit()
        self.anthropic_key_edit.setPlaceholderText("sk-ant-...")
        self.anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        anthropic_key = keyring.get_password(KEYRING_SERVICE, "anthropic_api_key")
        if anthropic_key:
            self.anthropic_key_edit.setText(anthropic_key)
            self.anthropic_key_edit.setPlaceholderText("(Enter new key to update)")
        anthropic_row.addWidget(self.anthropic_key_edit)
        
        anthropic_save_btn = QPushButton("Save")
        anthropic_save_btn.clicked.connect(lambda: self._save_api_key("anthropic_api_key", self.anthropic_key_edit.text()))
        anthropic_row.addWidget(anthropic_save_btn)
        ai_form.addRow("Anthropic API Key:", anthropic_row)
        
        ai_layout.addLayout(ai_form)
        layout.addWidget(ai_group)

        scripts_group = QGroupBox("Quick Scripts")
        scripts_layout = QVBoxLayout(scripts_group)
        scripts_layout.addWidget(QLabel("No scripts configured yet."))
        layout.addWidget(scripts_group)

        layout.addStretch()
    
    def _save_api_key(self, key_name: str, key_value: str):
        """Save API key to keyring."""
        if not key_value.strip():
            QMessageBox.warning(self, "Missing Key", "Please enter an API key.")
            return
        
        try:
            keyring.set_password(KEYRING_SERVICE, key_name, key_value.strip())
            provider = "OpenAI" if "openai" in key_name else "Anthropic"
            QMessageBox.information(self, "Success", f"{provider} API key saved successfully.")
        except Exception as e:
            logger.exception(f"Failed to save API key: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save API key: {e}")