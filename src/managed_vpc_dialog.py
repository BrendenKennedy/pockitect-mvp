from typing import Dict, List

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ManagedVpcDialog(QDialog):
    def __init__(self, regions: Dict[str, List[dict]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Associate Managed VPCs")
        self.setMinimumSize(700, 500)
        self._regions = regions
        self._controls: Dict[str, Dict[str, QComboBox]] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Existing VPCs were found. Please associate them to prod/dev/test "
                "or choose “Create new VPC”."
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, 1)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        for region, vpcs in sorted(self._regions.items()):
            box = QGroupBox(region)
            form = QFormLayout(box)
            self._controls[region] = {}

            for env in ("prod", "dev", "test"):
                combo = QComboBox()
                combo.addItem("Create new VPC", "__create__")
                for vpc in vpcs:
                    label = f"{vpc['id']} ({vpc.get('name') or 'unnamed'}) {vpc.get('cidr') or ''}"
                    combo.addItem(label, vpc["id"])
                form.addRow(env.upper(), combo)
                self._controls[region][env] = combo

            content_layout.addWidget(box)

        content_layout.addStretch()
        scroll.setWidget(content)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_assignments(self) -> Dict[str, Dict[str, str]]:
        result: Dict[str, Dict[str, str]] = {}
        for region, env_controls in self._controls.items():
            result[region] = {}
            for env, combo in env_controls.items():
                result[region][env] = combo.currentData()
        return result
