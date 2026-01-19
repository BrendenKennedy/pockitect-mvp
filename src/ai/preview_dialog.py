"""Preview dialog for generated YAML blueprints."""

from __future__ import annotations

from typing import List

import yaml
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QMessageBox,
)

from storage import save_project
from wizard.wizard import InfrastructureWizard


class YAMLPreviewDialog(QDialog):
    regenerate_requested = Signal()

    def __init__(self, blueprint: dict, errors: List[str] | None = None, parent=None):
        super().__init__(parent)
        self.blueprint = blueprint
        self.errors = errors or []
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Generated Blueprint Preview")
        self.setMinimumSize(700, 520)

        layout = QVBoxLayout(self)

        header = QLabel("Generated YAML Blueprint")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        if self.errors:
            error_text = "Validation issues:\n" + "\n".join(f"- {e}" for e in self.errors)
            error_label = QLabel(error_text)
            error_label.setStyleSheet("color: #e67e22;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

        self.yaml_view = QTextEdit()
        self.yaml_view.setReadOnly(True)
        self.yaml_view.setText(yaml.safe_dump(self.blueprint, sort_keys=False))
        layout.addWidget(self.yaml_view)

        button_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Project")
        self.save_btn.clicked.connect(self._save_project)
        button_row.addWidget(self.save_btn)

        self.edit_btn = QPushButton("Edit in Wizard")
        self.edit_btn.clicked.connect(self._open_wizard)
        button_row.addWidget(self.edit_btn)

        self.regenerate_btn = QPushButton("Regenerate")
        self.regenerate_btn.clicked.connect(self._on_regenerate)
        button_row.addWidget(self.regenerate_btn)

        button_row.addStretch()
        layout.addLayout(button_row)

    def _save_project(self):
        try:
            path = save_project(self.blueprint)
            QMessageBox.information(self, "Project Saved", f"Saved to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Failed to save project:\n{exc}")

    def _open_wizard(self):
        wizard = InfrastructureWizard(self)

        project = self.blueprint.get("project", {})
        compute = self.blueprint.get("compute", {})
        network = self.blueprint.get("network", {})
        data = self.blueprint.get("data", {})
        security = self.blueprint.get("security", {})

        wizard.project_page.set_data(project)
        wizard.compute_page.set_data(compute)
        wizard.network_page.set_data(network)
        wizard.data_page.set_data(self._map_data_for_wizard(data))
        wizard.security_page.set_data(self._map_security_for_wizard(security))

        wizard.exec()

    def _on_regenerate(self):
        self.regenerate_requested.emit()
        self.close()

    def _map_data_for_wizard(self, data: dict) -> dict:
        db = data.get("db", {}) or {}
        s3 = data.get("s3_bucket", {}) or {}

        db_enabled = db.get("status") not in ("skipped", None) or any(
            db.get(k) for k in ("engine", "instance_class", "allocated_storage_gb", "username")
        )
        s3_enabled = s3.get("status") not in ("skipped", None) or bool(s3.get("name"))

        return {
            "db": {
                "enabled": bool(db_enabled),
                "engine": db.get("engine"),
                "instance_class": db.get("instance_class"),
                "allocated_storage_gb": db.get("allocated_storage_gb"),
                "username": db.get("username"),
            },
            "s3_bucket": {
                "enabled": bool(s3_enabled),
                "name": s3.get("name"),
            },
        }

    def _map_security_for_wizard(self, security: dict) -> dict:
        kp = security.get("key_pair", {}) or {}
        cert = security.get("certificate", {}) or {}
        iam = security.get("iam_role", {}) or {}

        if kp.get("name"):
            kp_mode = "generate"
        elif kp.get("key_pair_id"):
            kp_mode = "existing"
        else:
            kp_mode = "none"

        cert_mode = "acm" if cert.get("domain") or cert.get("cert_arn") else "skip"
        iam_enabled = iam.get("status") != "skipped" if "status" in iam else bool(iam.get("role_name"))

        return {
            "key_pair": {
                "mode": kp_mode,
                "name": kp.get("name"),
            },
            "certificate": {
                "mode": cert_mode,
                "domain": cert.get("domain"),
            },
            "iam_role": {
                "enabled": bool(iam_enabled),
                "role_name": iam.get("role_name"),
            },
        }
