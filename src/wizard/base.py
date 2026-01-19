"""
Base classes and utilities for the wizard UI.
"""

from PySide6.QtWidgets import (
    QWizard,
    QWizardPage,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QGroupBox,
    QFormLayout,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class StyledWizardPage(QWizardPage):
    """
    Base class for wizard pages with consistent styling.
    """
    
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setTitle(title)
        self.setSubTitle(subtitle)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(16)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
    
    def add_section(self, title: str) -> QVBoxLayout:
        """Add a titled section with a group box."""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        self.main_layout.addWidget(group)
        return layout
    
    def add_form_section(self, title: str) -> QFormLayout:
        """Add a titled section with a form layout."""
        group = QGroupBox(title)
        layout = QFormLayout(group)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.main_layout.addWidget(group)
        return layout
    
    def create_labeled_input(self, label: str, placeholder: str = "") -> tuple[QLabel, QLineEdit]:
        """Create a label and line edit pair."""
        lbl = QLabel(label)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(32)
        return lbl, edit
    
    def create_labeled_combo(self, label: str, items: list[str] = None) -> tuple[QLabel, QComboBox]:
        """Create a label and combo box pair."""
        lbl = QLabel(label)
        combo = QComboBox()
        combo.setMinimumHeight(32)
        if items:
            combo.addItems(items)
        return lbl, combo
    
    def create_labeled_textarea(self, label: str, placeholder: str = "") -> tuple[QLabel, QTextEdit]:
        """Create a label and text area pair."""
        lbl = QLabel(label)
        text = QTextEdit()
        text.setPlaceholderText(placeholder)
        text.setMaximumHeight(120)
        return lbl, text


def create_info_label(text: str) -> QLabel:
    """Create an informational label with muted styling."""
    label = QLabel(text)
    label.setStyleSheet("color: #888; font-style: italic;")
    label.setWordWrap(True)
    return label


def create_separator() -> QFrame:
    """Create a horizontal separator line."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line
