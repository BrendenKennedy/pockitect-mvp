from typing import Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
)


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

        scripts_group = QGroupBox("Quick Scripts")
        scripts_layout = QVBoxLayout(scripts_group)
        scripts_layout.addWidget(QLabel("No scripts configured yet."))
        layout.addWidget(scripts_group)

        layout.addStretch()
