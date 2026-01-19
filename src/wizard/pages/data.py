"""
Wizard Page 4: Data Configuration (Optional)

Collects:
- Database: yes/no, engine, size, username, password
- S3 Bucket: yes/no, bucket name
"""

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QFormLayout, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox
)
from PySide6.QtCore import Qt

from ..base import StyledWizardPage, create_info_label

# Database engines
DB_ENGINES = [
    ("postgres", "PostgreSQL"),
    ("mysql", "MySQL"),
    ("mariadb", "MariaDB"),
]

# Database instance classes
DB_INSTANCE_CLASSES = [
    ("db.t3.micro", "db.t3.micro - 2 vCPU, 1 GB RAM (Free tier)"),
    ("db.t3.small", "db.t3.small - 2 vCPU, 2 GB RAM"),
    ("db.t3.medium", "db.t3.medium - 2 vCPU, 4 GB RAM"),
    ("db.t3.large", "db.t3.large - 2 vCPU, 8 GB RAM"),
    ("db.m5.large", "db.m5.large - 2 vCPU, 8 GB RAM"),
]


class DataPage(StyledWizardPage):
    """
    Fourth wizard page: configure optional database and S3 bucket.
    """
    
    def __init__(self, parent=None):
        super().__init__(
            title="Data (Optional)",
            subtitle="Configure optional database and storage resources.",
            parent=parent
        )
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Build the UI components."""
        # Database section
        self.db_check = QCheckBox("Create RDS Database")
        self.db_check.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.main_layout.addWidget(self.db_check)
        
        self.db_group = QGroupBox()
        self.db_group.setEnabled(False)
        db_form = QFormLayout(self.db_group)
        db_form.setSpacing(10)
        
        # Engine
        self.db_engine_combo = QComboBox()
        self.db_engine_combo.setMinimumHeight(32)
        for engine_id, engine_name in DB_ENGINES:
            self.db_engine_combo.addItem(engine_name, engine_id)
        db_form.addRow("Engine:", self.db_engine_combo)
        
        # Instance class
        self.db_class_combo = QComboBox()
        self.db_class_combo.setMinimumHeight(32)
        for class_id, class_name in DB_INSTANCE_CLASSES:
            self.db_class_combo.addItem(class_name, class_id)
        db_form.addRow("Instance Class:", self.db_class_combo)
        
        # Storage
        storage_layout = QHBoxLayout()
        self.db_storage_spin = QSpinBox()
        self.db_storage_spin.setRange(20, 1000)
        self.db_storage_spin.setValue(20)
        self.db_storage_spin.setSuffix(" GB")
        self.db_storage_spin.setMinimumWidth(100)
        storage_layout.addWidget(self.db_storage_spin)
        storage_layout.addWidget(create_info_label("Minimum 20 GB"))
        storage_layout.addStretch()
        db_form.addRow("Storage:", storage_layout)
        
        # Username
        self.db_username_edit = QLineEdit()
        self.db_username_edit.setPlaceholderText("admin")
        self.db_username_edit.setMinimumHeight(32)
        self.db_username_edit.setMaximumWidth(200)
        db_form.addRow("Master Username:", self.db_username_edit)
        
        # Password
        self.db_password_edit = QLineEdit()
        self.db_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_password_edit.setPlaceholderText("Enter password")
        self.db_password_edit.setMinimumHeight(32)
        self.db_password_edit.setMaximumWidth(200)
        db_form.addRow("Master Password:", self.db_password_edit)
        
        # Confirm password
        self.db_password_confirm_edit = QLineEdit()
        self.db_password_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_password_confirm_edit.setPlaceholderText("Confirm password")
        self.db_password_confirm_edit.setMinimumHeight(32)
        self.db_password_confirm_edit.setMaximumWidth(200)
        db_form.addRow("Confirm Password:", self.db_password_confirm_edit)
        
        # Password mismatch warning
        self.password_warning = QLabel("⚠ Passwords do not match")
        self.password_warning.setStyleSheet("color: red;")
        self.password_warning.setVisible(False)
        db_form.addRow("", self.password_warning)
        
        db_info = create_info_label(
            "RDS provides managed databases with automated backups, patching, and failover. "
            "db.t3.micro is free tier eligible for 750 hours/month."
        )
        db_form.addRow("", db_info)
        
        self.main_layout.addWidget(self.db_group)
        
        # Add some spacing
        self.main_layout.addSpacing(20)
        
        # S3 section
        self.s3_check = QCheckBox("Create S3 Bucket")
        self.s3_check.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.main_layout.addWidget(self.s3_check)
        
        self.s3_group = QGroupBox()
        self.s3_group.setEnabled(False)
        s3_form = QFormLayout(self.s3_group)
        s3_form.setSpacing(10)
        
        # Bucket name
        bucket_layout = QHBoxLayout()
        self.s3_name_edit = QLineEdit()
        self.s3_name_edit.setPlaceholderText("my-project-assets")
        self.s3_name_edit.setMinimumHeight(32)
        bucket_layout.addWidget(self.s3_name_edit)
        
        self.s3_region_suffix = QLabel("-us-east-1")
        self.s3_region_suffix.setStyleSheet("color: #666;")
        bucket_layout.addWidget(self.s3_region_suffix)
        bucket_layout.addStretch()
        s3_form.addRow("Bucket Name:", bucket_layout)
        
        s3_info = create_info_label(
            "S3 bucket names must be globally unique. Region suffix will be auto-appended. "
            "Buckets are great for static assets, backups, and file storage."
        )
        s3_form.addRow("", s3_info)
        
        self.main_layout.addWidget(self.s3_group)
        
        # Add stretch at the bottom
        self.main_layout.addStretch()
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.db_check.toggled.connect(self._on_db_toggled)
        self.s3_check.toggled.connect(self._on_s3_toggled)
        self.db_password_edit.textChanged.connect(self._check_passwords)
        self.db_password_confirm_edit.textChanged.connect(self._check_passwords)
    
    def _on_db_toggled(self, checked: bool):
        """Enable/disable database options."""
        self.db_group.setEnabled(checked)
    
    def _on_s3_toggled(self, checked: bool):
        """Enable/disable S3 options."""
        self.s3_group.setEnabled(checked)
    
    def _check_passwords(self):
        """Check if passwords match."""
        password = self.db_password_edit.text()
        confirm = self.db_password_confirm_edit.text()
        
        # Only show warning if both fields have content and don't match
        if password and confirm and password != confirm:
            self.password_warning.setVisible(True)
        else:
            self.password_warning.setVisible(False)
    
    def update_region(self, region: str):
        """Update the S3 region suffix when region changes."""
        self.s3_region_suffix.setText(f"-{region}")
    
    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        if self.db_check.isChecked():
            # Check username
            if not self.db_username_edit.text().strip():
                return False
            
            # Check passwords match
            password = self.db_password_edit.text()
            confirm = self.db_password_confirm_edit.text()
            if not password or password != confirm:
                self.password_warning.setVisible(True)
                return False
        
        if self.s3_check.isChecked():
            # Check bucket name
            if not self.s3_name_edit.text().strip():
                return False
        
        return True
    
    def get_data(self) -> dict:
        """
        Get the collected data from this page.
        
        Returns:
            Dict with data section
        """
        data = {
            "db": {
                "enabled": self.db_check.isChecked(),
                "engine": self.db_engine_combo.currentData() if self.db_check.isChecked() else None,
                "instance_class": self.db_class_combo.currentData() if self.db_check.isChecked() else None,
                "allocated_storage_gb": self.db_storage_spin.value() if self.db_check.isChecked() else None,
                "username": self.db_username_edit.text().strip() if self.db_check.isChecked() else None,
                # Note: password is NOT stored in the blueprint for security
                # It will be passed directly to boto3 at deploy time
                "password": None,
            },
            "s3_bucket": {
                "enabled": self.s3_check.isChecked(),
                "name": self.s3_name_edit.text().strip() if self.s3_check.isChecked() else None,
            }
        }
        return data
    
    def get_db_password(self) -> str:
        """
        Get the database password (not stored in blueprint).
        
        Returns:
            The password string, or empty string if not set
        """
        return self.db_password_edit.text()
    
    def set_data(self, data: dict):
        """
        Populate the page with existing data.
        
        Args:
            data: Dict with data section
        """
        if "db" in data:
            db = data["db"]
            self.db_check.setChecked(db.get("enabled", False))
            
            if "engine" in db and db["engine"]:
                for i in range(self.db_engine_combo.count()):
                    if self.db_engine_combo.itemData(i) == db["engine"]:
                        self.db_engine_combo.setCurrentIndex(i)
                        break
            
            if "instance_class" in db and db["instance_class"]:
                for i in range(self.db_class_combo.count()):
                    if self.db_class_combo.itemData(i) == db["instance_class"]:
                        self.db_class_combo.setCurrentIndex(i)
                        break
            
            if "allocated_storage_gb" in db and db["allocated_storage_gb"]:
                self.db_storage_spin.setValue(db["allocated_storage_gb"])
            
            if "username" in db and db["username"]:
                self.db_username_edit.setText(db["username"])
        
        if "s3_bucket" in data:
            s3 = data["s3_bucket"]
            self.s3_check.setChecked(s3.get("enabled", False))
            
            if "name" in s3 and s3["name"]:
                self.s3_name_edit.setText(s3["name"])
