"""
Dark mode stylesheet for Pockitect.
"""

DARK_THEME = """
/* Main Window */
QMainWindow, QDialog, QWizard {
    background-color: #1a1a2e;
    color: #eaeaea;
}

QWidget {
    background-color: #1a1a2e;
    color: #eaeaea;
    font-family: "Segoe UI", "Ubuntu", sans-serif;
}

/* Labels */
QLabel {
    color: #eaeaea;
    background: transparent;
}

/* Buttons */
QPushButton {
    background-color: #0f3460;
    color: #eaeaea;
    border: 1px solid #16213e;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #1a4a7a;
    border-color: #e94560;
}

QPushButton:pressed {
    background-color: #0a2540;
}

QPushButton:disabled {
    background-color: #2a2a4a;
    color: #666;
    border-color: #333;
}

/* Primary action buttons */
QPushButton[primary="true"], QPushButton#primaryButton {
    background-color: #e94560;
    border-color: #e94560;
}

QPushButton[primary="true"]:hover, QPushButton#primaryButton:hover {
    background-color: #ff6b6b;
}

/* Danger buttons */
QPushButton[danger="true"] {
    color: #ff6b6b;
}

/* Input fields */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #16213e;
    color: #eaeaea;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 8px;
    selection-background-color: #e94560;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #e94560;
}

QLineEdit:disabled, QTextEdit:disabled {
    background-color: #0d1525;
    color: #666;
}

/* Combo boxes */
QComboBox {
    background-color: #16213e;
    color: #eaeaea;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 8px;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #e94560;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #e94560;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #eaeaea;
    border: 1px solid #0f3460;
    selection-background-color: #e94560;
    selection-color: #fff;
    outline: none;
}

QComboBox QAbstractItemView::item {
    padding: 8px;
    min-height: 25px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #0f3460;
}

/* Spin boxes */
QSpinBox {
    background-color: #16213e;
    color: #eaeaea;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 6px;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #0f3460;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #e94560;
}

/* Check boxes */
QCheckBox {
    color: #eaeaea;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #0f3460;
    border-radius: 4px;
    background-color: #16213e;
}

QCheckBox::indicator:checked {
    background-color: #e94560;
    border-color: #e94560;
}

QCheckBox::indicator:hover {
    border-color: #e94560;
}

/* Radio buttons */
QRadioButton {
    color: #eaeaea;
    spacing: 8px;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #0f3460;
    border-radius: 10px;
    background-color: #16213e;
}

QRadioButton::indicator:checked {
    background-color: #e94560;
    border-color: #e94560;
}

QRadioButton::indicator:hover {
    border-color: #e94560;
}

/* Group boxes */
QGroupBox {
    color: #eaeaea;
    border: 1px solid #0f3460;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #e94560;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #0f3460;
    background-color: #1a1a2e;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #16213e;
    color: #aaa;
    padding: 12px 24px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #1a1a2e;
    color: #e94560;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #0f3460;
}

/* Lists */
QListWidget {
    background-color: #16213e;
    color: #eaeaea;
    border: 1px solid #0f3460;
    border-radius: 4px;
    outline: none;
}

QListWidget::item {
    padding: 12px;
    border-bottom: 1px solid #0f3460;
}

QListWidget::item:selected {
    background-color: #0f3460;
    color: #eaeaea;
}

QListWidget::item:hover:!selected {
    background-color: #1a3a5e;
}

/* Tables */
QTableWidget {
    background-color: #16213e;
    color: #eaeaea;
    border: 1px solid #0f3460;
    border-radius: 4px;
    gridline-color: #0f3460;
}

QTableWidget::item {
    padding: 8px;
}

QTableWidget::item:selected {
    background-color: #0f3460;
}

QHeaderView::section {
    background-color: #0f3460;
    color: #eaeaea;
    padding: 8px;
    border: none;
    border-right: 1px solid #16213e;
    font-weight: bold;
}

/* Scroll bars */
QScrollBar:vertical {
    background-color: #16213e;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #0f3460;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #e94560;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #16213e;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #0f3460;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #e94560;
}

/* Scroll area */
QScrollArea {
    border: none;
    background: transparent;
}

/* Progress bar */
QProgressBar {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    text-align: center;
    color: #eaeaea;
}

QProgressBar::chunk {
    background-color: #e94560;
    border-radius: 3px;
}

/* Wizard */
QWizard {
    background-color: #1a1a2e;
}

QWizard > QWidget {
    background-color: #1a1a2e;
}

/* Message boxes */
QMessageBox {
    background-color: #1a1a2e;
}

QMessageBox QLabel {
    color: #eaeaea;
}

/* Tooltips */
QToolTip {
    background-color: #0f3460;
    color: #eaeaea;
    border: 1px solid #e94560;
    padding: 5px;
    border-radius: 4px;
}

/* Status bar */
QStatusBar {
    background-color: #0f3460;
    color: #eaeaea;
}

/* Menu */
QMenu {
    background-color: #16213e;
    color: #eaeaea;
    border: 1px solid #0f3460;
}

QMenu::item {
    padding: 8px 20px;
}

QMenu::item:selected {
    background-color: #e94560;
}

/* Frame */
QFrame {
    border: none;
}

QFrame[frameShape="4"] { /* HLine */
    background-color: #0f3460;
    max-height: 1px;
}

/* AI chat bubbles */
QFrame[role="user"] {
    background-color: #1a4a7a;
    border: 1px solid #0f3460;
    border-radius: 10px;
}

QFrame[role="assistant"] {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 10px;
}

QFrame[role="tool"] {
    background-color: #0f3460;
    border: 1px solid #1a4a7a;
    border-radius: 999px;
}

QFrame[role="typing"] {
    background-color: #0f3460;
    border: 1px solid #16213e;
    border-radius: 8px;
}
"""
