"""
Wizard Page 6: Review & Deploy

Displays:
- Read-only summary of all choices
- "Deploy" button triggers boto3 sequence
"""

from PySide6.QtWidgets import (
    QLabel, QTextEdit, QVBoxLayout, QHBoxLayout, 
    QPushButton, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal

from ..base import StyledWizardPage, create_info_label


class ReviewPage(StyledWizardPage):
    """
    Sixth wizard page: review configuration and deploy.
    """
    
    # Signal emitted when deploy is requested
    deploy_requested = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(
            title="Review & Deploy",
            subtitle="Review your configuration and deploy to AWS.",
            parent=parent
        )
        self._blueprint = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the UI components."""
        # Summary scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.summary_widget = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_widget)
        self.summary_layout.setSpacing(16)
        
        scroll.setWidget(self.summary_widget)
        self.main_layout.addWidget(scroll, 1)
        
        # Info label
        info = create_info_label(
            "Review your configuration carefully. Once deployed, resources will incur AWS charges. "
            "You can go back to modify any settings."
        )
        self.main_layout.addWidget(info)
        
        # JSON preview toggle
        self.json_toggle = QPushButton("Show JSON Blueprint")
        self.json_toggle.setCheckable(True)
        self.json_toggle.clicked.connect(self._toggle_json)
        self.main_layout.addWidget(self.json_toggle)
        
        self.json_preview = QTextEdit()
        self.json_preview.setReadOnly(True)
        self.json_preview.setStyleSheet("font-family: monospace; background: #1e1e1e; color: #d4d4d4;")
        self.json_preview.setMinimumHeight(200)
        self.json_preview.setVisible(False)
        self.main_layout.addWidget(self.json_preview)
    
    def _toggle_json(self, checked: bool):
        """Toggle JSON preview visibility."""
        self.json_preview.setVisible(checked)
        self.json_toggle.setText("Hide JSON Blueprint" if checked else "Show JSON Blueprint")
    
    def _create_section(self, title: str, items: list[tuple[str, str]]) -> QWidget:
        """
        Create a summary section widget.
        
        Args:
            title: Section title
            items: List of (label, value) tuples
        
        Returns:
            QWidget containing the section
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Title
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 14px; color: #333; border-bottom: 1px solid #ccc; padding-bottom: 4px;")
        layout.addWidget(title_label)
        
        # Items
        for label, value in items:
            row = QHBoxLayout()
            row.setContentsMargins(10, 2, 0, 2)
            
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #666; min-width: 150px;")
            row.addWidget(lbl)
            
            val = QLabel(str(value) if value else "—")
            val.setStyleSheet("color: #333;")
            val.setWordWrap(True)
            row.addWidget(val, 1)
            
            layout.addLayout(row)
        
        return widget
    
    def update_summary(self, blueprint: dict):
        """
        Update the summary display with the current blueprint.
        
        Args:
            blueprint: The complete project blueprint dictionary
        """
        self._blueprint = blueprint
        
        # Clear existing content
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Project section
        project = blueprint.get("project", {})
        self.summary_layout.addWidget(self._create_section("Project", [
            ("Name", project.get("name")),
            ("Description", project.get("description")),
            ("Region", project.get("region")),
            ("Owner", project.get("owner")),
        ]))
        
        # Compute section
        compute = blueprint.get("compute", {})
        self.summary_layout.addWidget(self._create_section("Compute (EC2)", [
            ("Instance Type", compute.get("instance_type")),
            ("Image", compute.get("image_name", compute.get("image_id"))),
            ("User Data", "Yes" if compute.get("user_data") else "None"),
        ]))
        
        # Network section
        network = blueprint.get("network", {})
        vpc_env = network.get("vpc_env", "dev")
        rules_count = len(network.get("rules", []))
        rules_summary = f"{rules_count} rule(s)"
        if rules_count > 0:
            ports = [str(r.get("port")) for r in network.get("rules", [])[:5]]
            rules_summary += f" - ports: {', '.join(ports)}"
            if rules_count > 5:
                rules_summary += f" (+{rules_count - 5} more)"
        
        self.summary_layout.addWidget(self._create_section("Network", [
            ("VPC", f"Managed ({vpc_env})"),
            ("Subnet", network.get("subnet_type", "public").capitalize()),
            ("Firewall Rules", rules_summary),
        ]))
        
        # Data section
        data = blueprint.get("data", {})
        db = data.get("db", {})
        s3 = data.get("s3_bucket", {})
        
        data_items = []
        if db.get("enabled"):
            data_items.append(("Database", f"{db.get('engine')} - {db.get('instance_class')} ({db.get('allocated_storage_gb')} GB)"))
            data_items.append(("DB Username", db.get("username")))
        else:
            data_items.append(("Database", "None"))
        
        if s3.get("enabled"):
            data_items.append(("S3 Bucket", s3.get("name")))
        else:
            data_items.append(("S3 Bucket", "None"))
        
        self.summary_layout.addWidget(self._create_section("Data", data_items))
        
        # Security section
        security = blueprint.get("security", {})
        key_pair = security.get("key_pair", {})
        cert = security.get("certificate", {})
        iam = security.get("iam_role", {})
        
        key_display = "None"
        if key_pair.get("mode") == "generate":
            key_display = f"Generate new: {key_pair.get('name')}"
        elif key_pair.get("mode") == "existing":
            key_display = f"Use existing: {key_pair.get('name')}"
        
        cert_display = "Skip"
        if cert.get("mode") == "acm":
            cert_display = f"ACM: {cert.get('domain')}"
        elif cert.get("mode") == "custom":
            cert_display = "Custom certificate"
        
        self.summary_layout.addWidget(self._create_section("Security", [
            ("SSH Key", key_display),
            ("Certificate", cert_display),
            ("IAM Role", iam.get("role_name") if iam.get("enabled") else "None"),
        ]))
        
        # Add stretch at the end
        self.summary_layout.addStretch()
        
        # Update JSON preview
        import json
        # Create a clean blueprint for JSON display (remove sensitive data)
        clean_blueprint = self._clean_blueprint_for_display(blueprint)
        self.json_preview.setPlainText(json.dumps(clean_blueprint, indent=2))
    
    def _clean_blueprint_for_display(self, blueprint: dict) -> dict:
        """Remove sensitive data from blueprint for display."""
        import copy
        clean = copy.deepcopy(blueprint)
        
        # Remove passwords
        if "data" in clean and "db" in clean["data"]:
            if "password" in clean["data"]["db"]:
                clean["data"]["db"]["password"] = "***"
        
        # Remove private keys
        if "security" in clean and "key_pair" in clean["security"]:
            if "private_key_pem" in clean["security"]["key_pair"]:
                clean["security"]["key_pair"]["private_key_pem"] = "***"
        
        return clean
    
    def get_blueprint(self) -> dict:
        """
        Get the current blueprint.
        
        Returns:
            The complete project blueprint dictionary
        """
        return self._blueprint
