"""
Modern theme system for Pockitect with multi-theme support.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Theme:
    """Theme definition with colors and QSS stylesheet."""
    name: str
    display_name: str
    is_dark: bool
    qss_string: str
    colors: Dict[str, str]


class ThemeManager:
    """Manages themes and provides theme access."""
    
    _themes: Dict[str, Theme] = {}
    _default_theme_name = "modern_dark"
    
    @classmethod
    def _initialize_themes(cls):
        """Initialize all built-in themes."""
        if cls._themes:
            return
        
        cls._themes = {
            "modern_dark": cls._create_modern_dark_theme(),
            "modern_light": cls._create_modern_light_theme(),
            "high_contrast": cls._create_high_contrast_theme(),
            "ocean_blue": cls._create_ocean_blue_theme(),
            "forest_green": cls._create_forest_green_theme(),
        }
    
    @classmethod
    def get_theme(cls, name: str) -> Theme:
        """Get a theme by name."""
        cls._initialize_themes()
        return cls._themes.get(name, cls._themes[cls._default_theme_name])
    
    @classmethod
    def list_themes(cls) -> List[Theme]:
        """List all available themes."""
        cls._initialize_themes()
        return list(cls._themes.values())

    @classmethod
    def get_colors(cls, name: str) -> Dict[str, str]:
        """Get the theme color map by name."""
        return cls.get_theme(name).colors
    
    @classmethod
    def get_default_theme(cls) -> Theme:
        """Get the default theme."""
        cls._initialize_themes()
        return cls._themes[cls._default_theme_name]
    
    @classmethod
    def _create_modern_dark_theme(cls) -> Theme:
        """Modern Dark theme - enhanced version of original."""
        base_colors = {
            "bg_primary": "#1a1a2e",
            "bg_secondary": "#16213e",
            "bg_tertiary": "#0f3460",
            "bg_hover": "#1a4a7a",
            "bg_pressed": "#0a2540",
            "bg_disabled": "#2a2a4a",
            "text_primary": "#eaeaea",
            "text_secondary": "#aaa",
            "text_disabled": "#666",
            "accent": "#e94560",
            "accent_hover": "#ff6b6b",
            "border_primary": "#0f3460",
            "border_secondary": "#16213e",
            "border_accent": "#e94560",
            "selection": "#e94560",
        }
        status_colors = {
            "status_ok": "#a6e3a1",
            "status_warning": "#f9e2af",
            "status_info": "#89b4fa",
            "status_error": "#f38ba8",
            "status_muted": "#6c7086",
        }
        return Theme(
            name="modern_dark",
            display_name="Modern Dark",
            is_dark=True,
            qss_string=cls._generate_qss(**base_colors),
            colors={**base_colors, **status_colors},
        )
    
    @classmethod
    def _create_modern_light_theme(cls) -> Theme:
        """Modern Light theme - clean light theme."""
        base_colors = {
            "bg_primary": "#ffffff",
            "bg_secondary": "#f5f5f7",
            "bg_tertiary": "#e8e8ed",
            "bg_hover": "#e0e0e6",
            "bg_pressed": "#d1d1d9",
            "bg_disabled": "#f0f0f0",
            "text_primary": "#1d1d1f",
            "text_secondary": "#6e6e73",
            "text_disabled": "#999",
            "accent": "#007aff",
            "accent_hover": "#0051d5",
            "border_primary": "#d2d2d7",
            "border_secondary": "#e8e8ed",
            "border_accent": "#007aff",
            "selection": "#007aff",
        }
        status_colors = {
            "status_ok": "#2ecc71",
            "status_warning": "#f1c40f",
            "status_info": "#3498db",
            "status_error": "#e74c3c",
            "status_muted": "#8e8e93",
        }
        return Theme(
            name="modern_light",
            display_name="Modern Light",
            is_dark=False,
            qss_string=cls._generate_qss(**base_colors),
            colors={**base_colors, **status_colors},
        )
    
    @classmethod
    def _create_high_contrast_theme(cls) -> Theme:
        """High Contrast theme - enhanced accessibility."""
        base_colors = {
            "bg_primary": "#000000",
            "bg_secondary": "#1a1a1a",
            "bg_tertiary": "#2a2a2a",
            "bg_hover": "#3a3a3a",
            "bg_pressed": "#1a1a1a",
            "bg_disabled": "#1a1a1a",
            "text_primary": "#ffffff",
            "text_secondary": "#e0e0e0",
            "text_disabled": "#888",
            "accent": "#00ff00",
            "accent_hover": "#00cc00",
            "border_primary": "#ffffff",
            "border_secondary": "#666666",
            "border_accent": "#00ff00",
            "selection": "#00ff00",
        }
        status_colors = {
            "status_ok": "#00ff00",
            "status_warning": "#ffff00",
            "status_info": "#00ffff",
            "status_error": "#ff0000",
            "status_muted": "#bdbdbd",
        }
        return Theme(
            name="high_contrast",
            display_name="High Contrast",
            is_dark=True,
            qss_string=cls._generate_qss(**base_colors),
            colors={**base_colors, **status_colors},
        )
    
    @classmethod
    def _create_ocean_blue_theme(cls) -> Theme:
        """Ocean Blue theme - alternative dark with blue-green accents."""
        base_colors = {
            "bg_primary": "#0a1929",
            "bg_secondary": "#132f4c",
            "bg_tertiary": "#1e4976",
            "bg_hover": "#2a5f8f",
            "bg_pressed": "#0d1f33",
            "bg_disabled": "#1a2a3a",
            "text_primary": "#e3f2fd",
            "text_secondary": "#90caf9",
            "text_disabled": "#666",
            "accent": "#00bcd4",
            "accent_hover": "#00acc1",
            "border_primary": "#1e4976",
            "border_secondary": "#132f4c",
            "border_accent": "#00bcd4",
            "selection": "#00bcd4",
        }
        status_colors = {
            "status_ok": "#26a69a",
            "status_warning": "#ffca28",
            "status_info": "#4fc3f7",
            "status_error": "#ef5350",
            "status_muted": "#90caf9",
        }
        return Theme(
            name="ocean_blue",
            display_name="Ocean Blue",
            is_dark=True,
            qss_string=cls._generate_qss(**base_colors),
            colors={**base_colors, **status_colors},
        )
    
    @classmethod
    def _create_forest_green_theme(cls) -> Theme:
        """Forest Green theme - alternative dark with green accents."""
        base_colors = {
            "bg_primary": "#1a1f1a",
            "bg_secondary": "#1e3a1e",
            "bg_tertiary": "#2d5a2d",
            "bg_hover": "#3d7a3d",
            "bg_pressed": "#1a2f1a",
            "bg_disabled": "#2a3a2a",
            "text_primary": "#e8f5e9",
            "text_secondary": "#a5d6a7",
            "text_disabled": "#666",
            "accent": "#4caf50",
            "accent_hover": "#66bb6a",
            "border_primary": "#2d5a2d",
            "border_secondary": "#1e3a1e",
            "border_accent": "#4caf50",
            "selection": "#4caf50",
        }
        status_colors = {
            "status_ok": "#81c784",
            "status_warning": "#ffb74d",
            "status_info": "#64b5f6",
            "status_error": "#ef5350",
            "status_muted": "#a5d6a7",
        }
        return Theme(
            name="forest_green",
            display_name="Forest Green",
            is_dark=True,
            qss_string=cls._generate_qss(**base_colors),
            colors={**base_colors, **status_colors},
        )
    
    @classmethod
    def _generate_qss(
        cls,
        bg_primary: str,
        bg_secondary: str,
        bg_tertiary: str,
        bg_hover: str,
        bg_pressed: str,
        bg_disabled: str,
        text_primary: str,
        text_secondary: str,
        text_disabled: str,
        accent: str,
        accent_hover: str,
        border_primary: str,
        border_secondary: str,
        border_accent: str,
        selection: str,
    ) -> str:
        """Generate QSS stylesheet from color variables."""
        return f"""
/* Main Window */
QMainWindow, QDialog, QWizard {{
    background-color: {bg_primary};
    color: {text_primary};
}}

QWidget {{
    background-color: {bg_primary};
    color: {text_primary};
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 10pt;
    line-height: 1.6;
}}

/* Labels */
QLabel {{
    color: {text_primary};
    background: transparent;
    letter-spacing: 0.2px;
}}

/* Buttons */
QPushButton {{
    background-color: {bg_tertiary};
    color: {text_primary};
    border: 2px solid {border_primary};
    padding: 12px 20px;
    border-radius: 12px;
    font-weight: 500;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {bg_hover};
    border-color: {border_accent};
}}

QPushButton:pressed {{
    background-color: {bg_pressed};
    border-color: {border_accent};
}}

QPushButton:disabled {{
    background-color: {bg_disabled};
    color: {text_disabled};
    border-color: {border_secondary};
}}

/* Primary action buttons */
QPushButton[primary="true"], QPushButton#primaryButton {{
    background-color: {accent};
    border-color: {accent};
    font-weight: 600;
}}

QPushButton[primary="true"]:hover, QPushButton#primaryButton:hover {{
    background-color: {accent_hover};
    border-color: {accent_hover};
}}

/* Danger buttons */
QPushButton[danger="true"] {{
    color: {accent};
    border-color: {accent};
}}

QPushButton[danger="true"]:hover {{
    background-color: {accent};
    color: {text_primary};
}}

/* Input fields */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 2px solid {border_primary};
    border-radius: 8px;
    padding: 12px;
    selection-background-color: {selection};
    selection-color: {text_primary};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {border_accent};
    border-width: 2px;
}}

QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {bg_disabled};
    color: {text_disabled};
    border-color: {border_secondary};
}}

/* Combo boxes */
QComboBox {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 2px solid {border_primary};
    border-radius: 8px;
    padding: 12px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {border_accent};
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {accent};
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 2px solid {border_primary};
    selection-background-color: {selection};
    selection-color: {text_primary};
    outline: none;
    border-radius: 8px;
}}

QComboBox QAbstractItemView::item {{
    padding: 12px;
    min-height: 25px;
    border-radius: 4px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {bg_tertiary};
}}

/* Spin boxes */
QSpinBox {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 2px solid {border_primary};
    border-radius: 8px;
    padding: 10px;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {bg_tertiary};
    border: none;
    width: 20px;
    border-radius: 4px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {accent};
}}

/* Check boxes */
QCheckBox {{
    color: {text_primary};
    spacing: 10px;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {border_primary};
    border-radius: 6px;
    background-color: {bg_secondary};
}}

QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

QCheckBox::indicator:hover {{
    border-color: {border_accent};
}}

/* Radio buttons */
QRadioButton {{
    color: {text_primary};
    spacing: 10px;
}}

QRadioButton::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {border_primary};
    border-radius: 10px;
    background-color: {bg_secondary};
}}

QRadioButton::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

QRadioButton::indicator:hover {{
    border-color: {border_accent};
}}

/* Group boxes */
QGroupBox {{
    color: {text_primary};
    border: 2px solid {border_primary};
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: {accent};
}}

/* Tabs */
QTabWidget::pane {{
    border: 2px solid {border_primary};
    background-color: {bg_primary};
    border-radius: 8px;
}}

QTabBar::tab {{
    background-color: {bg_secondary};
    color: {text_secondary};
    padding: 14px 28px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {bg_primary};
    color: {accent};
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    background-color: {bg_tertiary};
    color: {text_primary};
}}

/* Lists */
QListWidget {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 2px solid {border_primary};
    border-radius: 8px;
    outline: none;
}}

QListWidget::item {{
    padding: 14px;
    border-bottom: 1px solid {border_primary};
}}

QListWidget::item:selected {{
    background-color: {bg_tertiary};
    color: {text_primary};
}}

QListWidget::item:hover:!selected {{
    background-color: {bg_hover};
}}

/* Tables */
QTableWidget {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 2px solid {border_primary};
    border-radius: 8px;
    gridline-color: {border_primary};
}}

QTableWidget::item {{
    padding: 12px;
}}

QTableWidget::item:selected {{
    background-color: {bg_tertiary};
}}

QHeaderView::section {{
    background-color: {bg_tertiary};
    color: {text_primary};
    padding: 12px;
    border: none;
    border-right: 1px solid {border_primary};
    font-weight: 600;
}}

/* Scroll bars */
QScrollBar:vertical {{
    background-color: {bg_secondary};
    width: 14px;
    border-radius: 7px;
}}

QScrollBar::handle:vertical {{
    background-color: {bg_tertiary};
    border-radius: 7px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {accent};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {bg_secondary};
    height: 14px;
    border-radius: 7px;
}}

QScrollBar::handle:horizontal {{
    background-color: {bg_tertiary};
    border-radius: 7px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {accent};
}}

/* Scroll area */
QScrollArea {{
    border: none;
    background: transparent;
}}

/* Progress bar */
QProgressBar {{
    background-color: {bg_secondary};
    border: 2px solid {border_primary};
    border-radius: 8px;
    text-align: center;
    color: {text_primary};
    font-weight: 500;
}}

QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 6px;
}}

/* Wizard */
QWizard {{
    background-color: {bg_primary};
}}

QWizard > QWidget {{
    background-color: {bg_primary};
}}

/* Message boxes */
QMessageBox {{
    background-color: {bg_primary};
}}

QMessageBox QLabel {{
    color: {text_primary};
}}

/* Tooltips */
QToolTip {{
    background-color: {bg_tertiary};
    color: {text_primary};
    border: 2px solid {border_accent};
    padding: 8px;
    border-radius: 8px;
    font-weight: 500;
}}

/* Status bar */
QStatusBar {{
    background-color: {bg_tertiary};
    color: {text_primary};
}}

/* Menu */
QMenu {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 2px solid {border_primary};
    border-radius: 8px;
}}

QMenu::item {{
    padding: 12px 24px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {accent};
    color: {text_primary};
}}

/* Frame */
QFrame {{
    border: none;
}}

QFrame[frameShape="4"] {{
    background-color: {border_primary};
    max-height: 2px;
}}

/* AI chat bubbles */
QFrame[role="user"] {{
    background-color: {bg_hover};
    border: 2px solid {border_primary};
    border-radius: 12px;
}}

QFrame[role="assistant"] {{
    background-color: {bg_secondary};
    border: 2px solid {border_primary};
    border-radius: 12px;
}}

QFrame[role="tool"] {{
    background-color: {bg_tertiary};
    border: 2px solid {border_accent};
    border-radius: 999px;
}}

QFrame[role="typing"] {{
    background-color: {bg_tertiary};
    border: 2px solid {border_secondary};
    border-radius: 8px;
}}
"""
    


# Backward compatibility - keep DARK_THEME for existing code
DARK_THEME = ThemeManager.get_default_theme().qss_string
