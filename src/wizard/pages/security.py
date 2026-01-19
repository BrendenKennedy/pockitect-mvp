"""
Wizard Page 5: Security Configuration

Collects:
- SSH Key: generate new (default) / use existing
- Certificate: skip / ACM (domain) / bring your own (PEM paste)
- IAM Role: auto-generate (review summary shown)
"""

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QCheckBox, QTextEdit,
    QFormLayout, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt
from datetime import datetime

from ..base import StyledWizardPage, create_info_label


class SecurityPage(StyledWizardPage):
    """
    Fifth wizard page: configure security settings.
    """
    
    def __init__(self, parent=None):
        super().__init__(
            title="Security",
            subtitle="Configure SSH keys, certificates, and IAM permissions.",
            parent=parent
        )
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Build the UI components."""
        # SSH Key section
        key_section = self.add_form_section("SSH Key Pair")
        
        key_widget = QWidget()
        key_layout = QVBoxLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        
        self.key_group = QButtonGroup(self)
        self.key_generate_radio = QRadioButton("Generate new key pair")
        self.key_existing_radio = QRadioButton("Use existing key pair")
        self.key_none_radio = QRadioButton("No SSH key (not recommended)")
        self.key_generate_radio.setChecked(True)
        self.key_group.addButton(self.key_generate_radio, 0)
        self.key_group.addButton(self.key_existing_radio, 1)
        self.key_group.addButton(self.key_none_radio, 2)
        
        key_layout.addWidget(self.key_generate_radio)
        
        # New key name input
        self.new_key_widget = QWidget()
        new_key_layout = QHBoxLayout(self.new_key_widget)
        new_key_layout.setContentsMargins(20, 5, 0, 5)
        new_key_layout.addWidget(QLabel("Key Name:"))
        self.new_key_name_edit = QLineEdit()
        self.new_key_name_edit.setPlaceholderText("my-project-key")
        self.new_key_name_edit.setMaximumWidth(250)
        new_key_layout.addWidget(self.new_key_name_edit)
        new_key_layout.addStretch()
        key_layout.addWidget(self.new_key_widget)
        
        key_layout.addWidget(self.key_existing_radio)
        
        # Existing key selection
        self.existing_key_widget = QWidget()
        existing_key_layout = QHBoxLayout(self.existing_key_widget)
        existing_key_layout.setContentsMargins(20, 5, 0, 5)
        existing_key_layout.addWidget(QLabel("Key Name:"))
        self.existing_key_combo = QComboBox()
        self.existing_key_combo.setMinimumWidth(200)
        self.existing_key_combo.addItem("(Will be fetched from AWS)", "")
        existing_key_layout.addWidget(self.existing_key_combo)
        existing_key_layout.addStretch()
        key_layout.addWidget(self.existing_key_widget)
        self.existing_key_widget.setVisible(False)
        
        key_layout.addWidget(self.key_none_radio)
        
        key_section.addRow("", key_widget)
        
        key_info = create_info_label(
            "A new key pair will be generated and the private key (.pem) saved to ~/.ssh/. "
            "You'll need this to SSH into your instance."
        )
        key_section.addRow("", key_info)
        
        # Certificate section
        cert_section = self.add_form_section("SSL/TLS Certificate")
        
        cert_widget = QWidget()
        cert_layout = QVBoxLayout(cert_widget)
        cert_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cert_group = QButtonGroup(self)
        self.cert_skip_radio = QRadioButton("Skip (no HTTPS)")
        self.cert_acm_radio = QRadioButton("Request ACM certificate")
        self.cert_custom_radio = QRadioButton("Bring your own certificate")
        self.cert_skip_radio.setChecked(True)
        self.cert_group.addButton(self.cert_skip_radio, 0)
        self.cert_group.addButton(self.cert_acm_radio, 1)
        self.cert_group.addButton(self.cert_custom_radio, 2)
        
        cert_layout.addWidget(self.cert_skip_radio)
        cert_layout.addWidget(self.cert_acm_radio)
        
        # ACM domain input
        self.acm_widget = QWidget()
        acm_layout = QHBoxLayout(self.acm_widget)
        acm_layout.setContentsMargins(20, 5, 0, 5)
        acm_layout.addWidget(QLabel("Domain:"))
        self.acm_domain_edit = QLineEdit()
        self.acm_domain_edit.setPlaceholderText("example.com")
        self.acm_domain_edit.setMaximumWidth(250)
        acm_layout.addWidget(self.acm_domain_edit)
        acm_layout.addStretch()
        cert_layout.addWidget(self.acm_widget)
        self.acm_widget.setVisible(False)
        
        cert_layout.addWidget(self.cert_custom_radio)
        
        # Custom cert input (hidden by default)
        self.custom_cert_widget = QWidget()
        custom_cert_layout = QVBoxLayout(self.custom_cert_widget)
        custom_cert_layout.setContentsMargins(20, 5, 0, 5)
        custom_cert_layout.addWidget(QLabel("Certificate PEM:"))
        self.custom_cert_edit = QTextEdit()
        self.custom_cert_edit.setPlaceholderText("-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----")
        self.custom_cert_edit.setMaximumHeight(80)
        self.custom_cert_edit.setStyleSheet("font-family: monospace;")
        custom_cert_layout.addWidget(self.custom_cert_edit)
        custom_cert_layout.addWidget(QLabel("Private Key PEM:"))
        self.custom_key_edit = QTextEdit()
        self.custom_key_edit.setPlaceholderText("-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----")
        self.custom_key_edit.setMaximumHeight(80)
        self.custom_key_edit.setStyleSheet("font-family: monospace;")
        custom_cert_layout.addWidget(self.custom_key_edit)
        cert_layout.addWidget(self.custom_cert_widget)
        self.custom_cert_widget.setVisible(False)
        
        cert_section.addRow("", cert_widget)
        
        cert_info = create_info_label(
            "ACM certificates are free and auto-renew. DNS validation will be required. "
            "Skip if you don't need HTTPS or will configure it later."
        )
        cert_section.addRow("", cert_info)
        
        # IAM Role section
        iam_section = self.add_form_section("IAM Instance Role")
        
        self.iam_check = QCheckBox("Create IAM role for EC2 instance")
        self.iam_check.setChecked(True)
        iam_section.addRow("", self.iam_check)
        
        self.iam_group = QGroupBox("Role Configuration")
        iam_form = QFormLayout(self.iam_group)
        
        # Role name
        self.iam_role_name_edit = QLineEdit()
        self.iam_role_name_edit.setPlaceholderText("pockitect-my-project-role")
        self.iam_role_name_edit.setMaximumWidth(300)
        iam_form.addRow("Role Name:", self.iam_role_name_edit)
        
        # Permissions summary
        self.iam_perms_label = QLabel()
        self.iam_perms_label.setWordWrap(True)
        self.iam_perms_label.setStyleSheet("background: #f5f5f5; padding: 10px; border-radius: 4px;")
        self._update_iam_summary()
        iam_form.addRow("Permissions:", self.iam_perms_label)
        
        iam_section.addRow("", self.iam_group)
        
        iam_info = create_info_label(
            "An IAM role allows your EC2 instance to access other AWS services securely "
            "without storing credentials on the instance."
        )
        iam_section.addRow("", iam_info)
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.key_group.buttonClicked.connect(self._on_key_choice_changed)
        self.cert_group.buttonClicked.connect(self._on_cert_choice_changed)
        self.iam_check.toggled.connect(self._on_iam_toggled)
    
    def _on_key_choice_changed(self):
        """Show/hide key inputs based on selection."""
        self.new_key_widget.setVisible(self.key_generate_radio.isChecked())
        self.existing_key_widget.setVisible(self.key_existing_radio.isChecked())
    
    def _on_cert_choice_changed(self):
        """Show/hide certificate inputs based on selection."""
        self.acm_widget.setVisible(self.cert_acm_radio.isChecked())
        self.custom_cert_widget.setVisible(self.cert_custom_radio.isChecked())
    
    def _on_iam_toggled(self, checked: bool):
        """Enable/disable IAM options."""
        self.iam_group.setEnabled(checked)
    
    def _update_iam_summary(self, s3_enabled: bool = False, rds_enabled: bool = False):
        """Update the IAM permissions summary based on selected services."""
        perms = ["ec2:DescribeInstances (basic EC2 access)"]
        
        if s3_enabled:
            perms.append("s3:GetObject, s3:PutObject (bucket access)")
        
        if rds_enabled:
            perms.append("rds:DescribeDBInstances (database info)")
        
        perms.append("logs:CreateLogGroup, logs:PutLogEvents (CloudWatch)")
        
        self.iam_perms_label.setText("• " + "\n• ".join(perms))
    
    def update_from_data_page(self, s3_enabled: bool, rds_enabled: bool):
        """Update IAM summary based on data page selections."""
        self._update_iam_summary(s3_enabled, rds_enabled)
    
    def update_project_name(self, project_name: str):
        """Update default names based on project name."""
        from storage import slugify
        slug = slugify(project_name) if project_name else "my-project"
        date_suffix = datetime.now().strftime("%Y%m%d")
        
        if not self.new_key_name_edit.text():
            self.new_key_name_edit.setText(f"{slug}-key-{date_suffix}")
        
        if not self.iam_role_name_edit.text():
            self.iam_role_name_edit.setText(f"pockitect-{slug}-role")
    
    def get_data(self) -> dict:
        """
        Get the collected data from this page.
        
        Returns:
            Dict with security section data
        """
        # Key pair
        if self.key_generate_radio.isChecked():
            key_pair = {
                "mode": "generate",
                "name": self.new_key_name_edit.text().strip() or None,
            }
        elif self.key_existing_radio.isChecked():
            key_pair = {
                "mode": "existing",
                "name": self.existing_key_combo.currentData() or None,
            }
        else:
            key_pair = {
                "mode": "none",
                "name": None,
            }
        
        # Certificate
        if self.cert_skip_radio.isChecked():
            certificate = {
                "mode": "skip",
                "domain": None,
            }
        elif self.cert_acm_radio.isChecked():
            certificate = {
                "mode": "acm",
                "domain": self.acm_domain_edit.text().strip() or None,
            }
        else:
            certificate = {
                "mode": "custom",
                "domain": None,
                # Note: actual cert content would be handled separately for security
            }
        
        # IAM role
        iam_role = {
            "enabled": self.iam_check.isChecked(),
            "role_name": self.iam_role_name_edit.text().strip() if self.iam_check.isChecked() else None,
        }
        
        return {
            "key_pair": key_pair,
            "certificate": certificate,
            "iam_role": iam_role,
        }
    
    def set_data(self, data: dict):
        """
        Populate the page with existing data.
        
        Args:
            data: Dict with security section data
        """
        if "key_pair" in data:
            kp = data["key_pair"]
            mode = kp.get("mode", "generate")
            
            if mode == "generate":
                self.key_generate_radio.setChecked(True)
                if kp.get("name"):
                    self.new_key_name_edit.setText(kp["name"])
            elif mode == "existing":
                self.key_existing_radio.setChecked(True)
            else:
                self.key_none_radio.setChecked(True)
            
            self._on_key_choice_changed()
        
        if "certificate" in data:
            cert = data["certificate"]
            mode = cert.get("mode", "skip")
            
            if mode == "skip":
                self.cert_skip_radio.setChecked(True)
            elif mode == "acm":
                self.cert_acm_radio.setChecked(True)
                if cert.get("domain"):
                    self.acm_domain_edit.setText(cert["domain"])
            else:
                self.cert_custom_radio.setChecked(True)
            
            self._on_cert_choice_changed()
        
        if "iam_role" in data:
            iam = data["iam_role"]
            self.iam_check.setChecked(iam.get("enabled", True))
            if iam.get("role_name"):
                self.iam_role_name_edit.setText(iam["role_name"])
