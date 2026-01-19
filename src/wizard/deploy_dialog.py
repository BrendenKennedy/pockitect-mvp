"""
Deployment Progress Dialog

Shows real-time progress of AWS resource deployment.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Signal

from deploy_worker import ProjectDeployWorker


class DeploymentDialog(QDialog):
    """Dialog showing deployment progress via Redis status updates."""

    deployment_finished = Signal(bool, dict)

    def __init__(self, blueprint: dict, db_password: str = None, parent=None):
        super().__init__(parent)
        self.blueprint = blueprint
        self.db_password = db_password
        self.worker = None

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Deploying Infrastructure")
        self.setMinimumSize(600, 420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("Deploying AWS Infrastructure")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        project = self.blueprint.get("project", {})
        info = QLabel(
            f"Project: {project.get('name', 'Unknown')} | Region: {project.get('region', 'Unknown')}"
        )
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)

        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(140)
        self.log_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        button_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def start_deployment(self):
        if self.worker:
            return
        self._log("Starting deployment...")
        self.status_label.setText("Deploying...")
        self.worker = ProjectDeployWorker(
            self.blueprint, db_password=self.db_password, parent=self
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_deployment_finished)
        self.worker.start()

    def _on_progress(self, message: str, step: int, total: int):
        self.status_label.setText(message)
        if step >= 0 and total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(step)
            self.status_label.setText(f"{message} ({step}/{total})")
        else:
            self.progress_bar.setRange(0, 0)
        self._log(message)

    def _on_deployment_finished(self, success: bool, message: str):
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)

        if success:
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            self._log("=" * 40)
            self._log("Deployment completed successfully!")
            self.deployment_finished.emit(True, self.blueprint)
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
            self._log("=" * 40)
            self._log(message or "Deployment failed")
            self.deployment_finished.emit(False, self.blueprint)

    def _on_cancel(self):
        reply = QMessageBox.question(
            self,
            "Cancel Deployment",
            "Are you sure you want to cancel the deployment?\n\n"
            "Note: Resources that have already been created will NOT be automatically deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._log("Cancellation requested...")
            if self.worker:
                self.worker.requestInterruption()
            self.cancel_btn.setEnabled(False)

    def _log(self, message: str):
        self.log_text.append(message)
