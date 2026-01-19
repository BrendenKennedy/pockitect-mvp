"""
Wizard Page 1: Project Basics

Collects:
- Project name (slug auto-generated)
- Short description
- Region (dropdown)
- Owner name (optional)
"""

from PySide6.QtWidgets import QLabel, QLineEdit, QComboBox, QFormLayout, QDoubleSpinBox
from PySide6.QtCore import Signal

from ..base import StyledWizardPage, create_info_label

# AWS regions (common ones for MVP)
AWS_REGIONS = [
    ("us-east-1", "US East (N. Virginia)"),
    ("us-east-2", "US East (Ohio)"),
    ("us-west-1", "US West (N. California)"),
    ("us-west-2", "US West (Oregon)"),
    ("eu-west-1", "EU (Ireland)"),
    ("eu-west-2", "EU (London)"),
    ("eu-central-1", "EU (Frankfurt)"),
    ("ap-northeast-1", "Asia Pacific (Tokyo)"),
    ("ap-southeast-1", "Asia Pacific (Singapore)"),
    ("ap-southeast-2", "Asia Pacific (Sydney)"),
]


class ProjectBasicsPage(StyledWizardPage):
    """
    First wizard page: collect project metadata.
    """
    
    def __init__(self, parent=None):
        super().__init__(
            title="Project Basics",
            subtitle="Enter the basic information for your AWS infrastructure project.",
            parent=parent
        )
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Build the UI components."""
        # Project details section
        form = self.add_form_section("Project Details")
        
        # Project name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., My Blog Backend")
        self.name_edit.setMinimumHeight(32)
        form.addRow("Project Name:", self.name_edit)
        
        # Auto-generated slug preview
        self.slug_label = QLabel("—")
        self.slug_label.setStyleSheet("color: #666; font-family: monospace;")
        form.addRow("Slug:", self.slug_label)
        
        # Description
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Brief description of what this project deploys")
        self.description_edit.setMinimumHeight(32)
        form.addRow("Description:", self.description_edit)
        
        # Owner
        self.owner_edit = QLineEdit()
        self.owner_edit.setPlaceholderText("Your name or team name (optional)")
        self.owner_edit.setMinimumHeight(32)
        form.addRow("Owner:", self.owner_edit)
        
        # Cost
        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setMinimum(0.0)
        self.cost_spin.setMaximum(999999.99)
        self.cost_spin.setDecimals(2)
        self.cost_spin.setPrefix("$")
        self.cost_spin.setSuffix(" /month")
        self.cost_spin.setSpecialValueText("Not set")
        self.cost_spin.setMinimumHeight(32)
        self.cost_spin.setValue(0.0)  # Default to "Not set"
        form.addRow("Estimated Cost:", self.cost_spin)
        
        # Region section
        region_form = self.add_form_section("AWS Region")
        
        self.region_combo = QComboBox()
        self.region_combo.setMinimumHeight(32)
        for region_id, region_name in AWS_REGIONS:
            self.region_combo.addItem(f"{region_name} ({region_id})", region_id)
        # Default to us-east-1
        self.region_combo.setCurrentIndex(0)
        region_form.addRow("Region:", self.region_combo)
        
        # Info label
        info = create_info_label(
            "Choose the AWS region closest to your users. "
            "All resources will be created in this region."
        )
        region_form.addRow("", info)
        
        # Register fields for wizard validation
        self.registerField("project_name*", self.name_edit)
        self.registerField("project_description", self.description_edit)
        self.registerField("project_owner", self.owner_edit)
        self.registerField("project_region", self.region_combo, "currentData")
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.name_edit.textChanged.connect(self._update_slug)
    
    def _update_slug(self, text: str):
        """Update the slug preview as the user types."""
        from storage import slugify
        if text.strip():
            slug = slugify(text)
            self.slug_label.setText(slug)
        else:
            self.slug_label.setText("—")
    
    def get_data(self) -> dict:
        """
        Get the collected data from this page.
        
        Returns:
            Dict with project section data
        """
        from storage import slugify
        
        name = self.name_edit.text().strip()
        cost_value = self.cost_spin.value()
        cost = cost_value if cost_value > 0 else None
        return {
            "name": name,
            "slug": slugify(name) if name else "",
            "description": self.description_edit.text().strip(),
            "owner": self.owner_edit.text().strip(),
            "region": self.region_combo.currentData(),
            "cost": cost,
        }
    
    def set_data(self, data: dict):
        """
        Populate the page with existing data.
        
        Args:
            data: Dict with project section data
        """
        if "name" in data:
            self.name_edit.setText(data["name"])
        if "description" in data:
            self.description_edit.setText(data["description"])
        if "owner" in data:
            self.owner_edit.setText(data["owner"])
        if "region" in data:
            # Find and select the matching region
            for i in range(self.region_combo.count()):
                if self.region_combo.itemData(i) == data["region"]:
                    self.region_combo.setCurrentIndex(i)
                    break
        if "cost" in data:
            cost = data["cost"]
            if cost is not None and isinstance(cost, (int, float)) and cost > 0:
                self.cost_spin.setValue(float(cost))
            else:
                self.cost_spin.setValue(0.0)
