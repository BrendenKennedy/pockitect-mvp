"""Model selector widget for choosing LLM provider."""

from __future__ import annotations

import logging
from typing import Optional
import keyring

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QMessageBox,
    QFormLayout,
    QDialogButtonBox,
)

from .models.config import list_models, get_model_config, get_default_model
from .models.factory import ModelFactory

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "PockitectApp"


class APIKeyDialog(QDialog):
    """Dialog for entering API keys."""
    
    def __init__(self, provider: str, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.api_key = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle(f"{self.provider.title()} API Key")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText(f"Enter your {self.provider} API key")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key:", self.key_edit)
        
        layout.addLayout(form)
        
        # Try to load existing key
        try:
            key_name = f"{self.provider.lower()}_api_key"
            existing_key = keyring.get_password(KEYRING_SERVICE, key_name)
            if existing_key:
                self.key_edit.setText(existing_key)
                self.key_edit.setPlaceholderText("(Enter new key to update)")
        except Exception:
            pass
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _on_accept(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing Key", "Please enter an API key.")
            return
        
        self.api_key = key
        self.accept()


class ModelSelectorWidget(QWidget):
    """Widget for selecting LLM model with connection status."""
    
    model_changed = Signal(str)  # Emitted when model selection changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_model_id = get_default_model()
        self._setup_ui()
        self._update_status()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        label = QLabel("Model:")
        layout.addWidget(label)
        
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        self._populate_models()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        layout.addWidget(self.model_combo)
        
        self.status_label = QLabel()
        self.status_label.setMinimumWidth(80)
        layout.addWidget(self.status_label)
        
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setMaximumWidth(30)
        self.settings_btn.setToolTip("Model Settings")
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        layout.addWidget(self.settings_btn)
        
        layout.addStretch()
    
    def _populate_models(self):
        """Populate model combo box with available models."""
        self.model_combo.clear()
        models = list_models()
        
        for model_config in models:
            display_name = model_config.display_name
            # Check if model is available
            if ModelFactory.is_model_available(model_config.id):
                status = "✓"
            elif model_config.requires_api_key:
                status = "🔑"  # Needs API key
            else:
                status = "✗"  # Not available
            
            self.model_combo.addItem(f"{status} {display_name}", model_config.id)
        
        # Set default selection
        default_id = get_default_model()
        index = self.model_combo.findData(default_id)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
    
    def _on_model_changed(self):
        """Handle model selection change."""
        index = self.model_combo.currentIndex()
        if index < 0:
            return
        
        model_id = self.model_combo.itemData(index)
        if not model_id:
            return
        
        self.current_model_id = model_id
        self._update_status()
        self.model_changed.emit(model_id)
    
    def _update_status(self):
        """Update connection status display."""
        config = get_model_config(self.current_model_id)
        if not config:
            self.status_label.setText("")
            return
        
        if ModelFactory.is_model_available(self.current_model_id):
            self.status_label.setText("✓ Online")
            self.status_label.setStyleSheet("color: #4ade80;")
        elif config.requires_api_key:
            self.status_label.setText("🔑 API Key Needed")
            self.status_label.setStyleSheet("color: #fbbf24;")
        else:
            self.status_label.setText("✗ Offline")
            self.status_label.setStyleSheet("color: #f87171;")
    
    def _on_settings_clicked(self):
        """Open settings dialog for current model."""
        config = get_model_config(self.current_model_id)
        if not config or not config.requires_api_key:
            QMessageBox.information(
                self,
                "No Settings",
                f"{config.display_name if config else 'This model'} does not require API key configuration."
            )
            return
        
        # Show API key dialog
        provider = config.provider.title()
        dialog = APIKeyDialog(provider, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.api_key:
            try:
                keyring.set_password(KEYRING_SERVICE, config.api_key_name, dialog.api_key)
                QMessageBox.information(self, "Success", f"{provider} API key saved.")
                self._populate_models()
                self._update_status()
            except Exception as e:
                logger.exception("Failed to save API key")
                QMessageBox.critical(self, "Error", f"Failed to save API key: {e}")
    
    def get_current_model_id(self) -> str:
        """Get currently selected model ID."""
        return self.current_model_id
    
    def set_model(self, model_id: str):
        """Set the selected model."""
        index = self.model_combo.findData(model_id)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
