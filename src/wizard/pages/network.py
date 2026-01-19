"""
Wizard Page 3: Network Configuration

Collects:
- VPC: default or new
- Subnet: public (default)
- Firewall rules (security group rules)
"""

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QFormLayout, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QRadioButton, QButtonGroup, QWidget
)
from PySide6.QtCore import Qt

from ..base import StyledWizardPage, create_info_label, create_separator

# Common firewall rule presets
RULE_PRESETS = {
    "ssh": {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
    "http": {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"},
    "https": {"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTPS"},
    "mysql": {"port": 3306, "protocol": "tcp", "cidr": "10.0.0.0/8", "description": "MySQL (private)"},
    "postgres": {"port": 5432, "protocol": "tcp", "cidr": "10.0.0.0/8", "description": "PostgreSQL (private)"},
    "redis": {"port": 6379, "protocol": "tcp", "cidr": "10.0.0.0/8", "description": "Redis (private)"},
}


class NetworkPage(StyledWizardPage):
    """
    Third wizard page: configure VPC, subnet, and security group.
    """
    
    def __init__(self, parent=None):
        super().__init__(
            title="Network",
            subtitle="Configure your VPC, subnet, and firewall rules.",
            parent=parent
        )
        self._rules = []
        self._setup_ui()
        self._connect_signals()
        # Add default rules
        self._add_rule_preset("ssh")
        self._add_rule_preset("http")
        self._add_rule_preset("https")
    
    def _setup_ui(self):
        """Build the UI components."""
        # VPC section
        vpc_form = self.add_form_section("Virtual Private Cloud (VPC)")
        
        # VPC environment choice
        vpc_widget = QWidget()
        vpc_layout = QVBoxLayout(vpc_widget)
        vpc_layout.setContentsMargins(0, 0, 0, 0)

        self.vpc_group = QButtonGroup(self)
        self.vpc_prod_radio = QRadioButton("Use PROD managed VPC")
        self.vpc_dev_radio = QRadioButton("Use DEV managed VPC")
        self.vpc_test_radio = QRadioButton("Use TEST managed VPC")
        self.vpc_dev_radio.setChecked(True)
        self.vpc_group.addButton(self.vpc_prod_radio, 0)
        self.vpc_group.addButton(self.vpc_dev_radio, 1)
        self.vpc_group.addButton(self.vpc_test_radio, 2)

        vpc_layout.addWidget(self.vpc_prod_radio)
        vpc_layout.addWidget(self.vpc_dev_radio)
        vpc_layout.addWidget(self.vpc_test_radio)
        vpc_form.addRow("", vpc_widget)

        info = create_info_label(
            "Projects use managed VPCs that stay up per region (prod/dev/test). "
            "Select which environment this project should use."
        )
        vpc_form.addRow("", info)
        
        # Subnet section
        subnet_form = self.add_form_section("Subnet")
        
        self.subnet_combo = QComboBox()
        self.subnet_combo.setMinimumHeight(32)
        self.subnet_combo.addItem("Public subnet (auto-assign public IP)", "public")
        self.subnet_combo.addItem("Private subnet (no public IP)", "private")
        subnet_form.addRow("Subnet Type:", self.subnet_combo)
        
        info2 = create_info_label(
            "Public subnets have direct internet access via an Internet Gateway. "
            "Private subnets require a NAT Gateway for outbound internet access."
        )
        subnet_form.addRow("", info2)
        
        # Firewall rules section
        rules_section = self.add_section("Firewall Rules (Security Group)")
        
        # Preset buttons
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Quick add:"))
        
        for preset_name in ["ssh", "http", "https", "mysql", "postgres"]:
            btn = QPushButton(preset_name.upper())
            btn.setMaximumWidth(80)
            btn.clicked.connect(lambda checked, p=preset_name: self._add_rule_preset(p))
            preset_layout.addWidget(btn)
        preset_layout.addStretch()
        rules_section.addLayout(preset_layout)
        
        # Rules table
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(5)
        self.rules_table.setHorizontalHeaderLabels(["Port", "Protocol", "Source CIDR", "Description", ""])
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.rules_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.rules_table.setColumnWidth(0, 70)
        self.rules_table.setColumnWidth(1, 80)
        self.rules_table.setColumnWidth(4, 60)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setMinimumHeight(150)
        rules_section.addWidget(self.rules_table)
        
        # Manual rule input section
        manual_group = QWidget()
        manual_group.setStyleSheet("QWidget { background-color: transparent; }")
        manual_layout = QVBoxLayout(manual_group)
        manual_layout.setContentsMargins(0, 10, 0, 0)
        
        manual_label = QLabel("Add Custom Rule:")
        manual_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        manual_layout.addWidget(manual_label)
        
        # Row 1: Port and Protocol
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Port:"))
        self.custom_port_spin = QSpinBox()
        self.custom_port_spin.setRange(1, 65535)
        self.custom_port_spin.setValue(8080)
        self.custom_port_spin.setMinimumWidth(100)
        row1.addWidget(self.custom_port_spin)
        
        row1.addSpacing(20)
        row1.addWidget(QLabel("Protocol:"))
        self.custom_protocol_combo = QComboBox()
        self.custom_protocol_combo.addItems(["tcp", "udp", "icmp"])
        self.custom_protocol_combo.setMinimumWidth(80)
        row1.addWidget(self.custom_protocol_combo)
        row1.addStretch()
        manual_layout.addLayout(row1)
        
        # Row 2: CIDR and Description
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Source CIDR:"))
        self.custom_cidr_edit = QLineEdit()
        self.custom_cidr_edit.setText("0.0.0.0/0")
        self.custom_cidr_edit.setPlaceholderText("0.0.0.0/0 or 10.0.0.0/8")
        self.custom_cidr_edit.setMinimumWidth(150)
        row2.addWidget(self.custom_cidr_edit)
        
        row2.addSpacing(20)
        row2.addWidget(QLabel("Description:"))
        self.custom_desc_edit = QLineEdit()
        self.custom_desc_edit.setPlaceholderText("e.g., API Server")
        self.custom_desc_edit.setMinimumWidth(150)
        row2.addWidget(self.custom_desc_edit)
        row2.addStretch()
        manual_layout.addLayout(row2)
        
        # Add button
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Rule")
        add_btn.setMinimumWidth(120)
        add_btn.clicked.connect(self._add_custom_rule)
        btn_row.addWidget(add_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all_rules)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        manual_layout.addLayout(btn_row)
        
        rules_section.addWidget(manual_group)
        
        info3 = create_info_label(
            "0.0.0.0/0 allows access from anywhere. Use specific CIDR blocks (e.g., your IP) "
            "for sensitive ports like SSH. Press Enter in any field to quickly add the rule."
        )
        rules_section.addWidget(info3)
    
    def _connect_signals(self):
        """Connect UI signals."""
        # Allow Enter key to add rules from text fields
        self.custom_cidr_edit.returnPressed.connect(self._add_custom_rule)
        self.custom_desc_edit.returnPressed.connect(self._add_custom_rule)
    
    def _add_rule_preset(self, preset_name: str):
        """Add a rule from presets."""
        if preset_name in RULE_PRESETS:
            rule = RULE_PRESETS[preset_name].copy()
            # Check if rule already exists
            for existing in self._rules:
                if existing["port"] == rule["port"] and existing["protocol"] == rule["protocol"]:
                    return  # Already exists
            self._rules.append(rule)
            self._refresh_rules_table()
    
    def _add_custom_rule(self):
        """Add a custom rule from the input fields."""
        rule = {
            "port": self.custom_port_spin.value(),
            "protocol": self.custom_protocol_combo.currentText(),
            "cidr": self.custom_cidr_edit.text().strip() or "0.0.0.0/0",
            "description": self.custom_desc_edit.text().strip() or f"Port {self.custom_port_spin.value()}",
        }
        # Check for duplicates
        for existing in self._rules:
            if existing["port"] == rule["port"] and existing["protocol"] == rule["protocol"]:
                return  # Already exists
        self._rules.append(rule)
        self._refresh_rules_table()
        # Clear inputs
        self.custom_desc_edit.clear()
    
    def _remove_rule(self, index: int):
        """Remove a rule by index."""
        if 0 <= index < len(self._rules):
            self._rules.pop(index)
            self._refresh_rules_table()
    
    def _clear_all_rules(self):
        """Clear all rules."""
        self._rules.clear()
        self._refresh_rules_table()
    
    def _refresh_rules_table(self):
        """Refresh the rules table from the internal list."""
        self.rules_table.setRowCount(len(self._rules))
        
        for i, rule in enumerate(self._rules):
            self.rules_table.setItem(i, 0, QTableWidgetItem(str(rule["port"])))
            self.rules_table.setItem(i, 1, QTableWidgetItem(rule["protocol"]))
            self.rules_table.setItem(i, 2, QTableWidgetItem(rule["cidr"]))
            self.rules_table.setItem(i, 3, QTableWidgetItem(rule["description"]))
            
            # Delete button
            del_btn = QPushButton("×")
            del_btn.setMaximumWidth(40)
            del_btn.setStyleSheet("color: #ff6b6b; font-weight: bold; font-size: 16px;")
            del_btn.clicked.connect(lambda checked, idx=i: self._remove_rule(idx))
            self.rules_table.setCellWidget(i, 4, del_btn)
        
        # Update row heights for better visibility
        for i in range(self.rules_table.rowCount()):
            self.rules_table.setRowHeight(i, 35)
    
    def get_data(self) -> dict:
        """
        Get the collected data from this page.
        
        Returns:
            Dict with network section data
        """
        vpc_env = "dev"
        if self.vpc_prod_radio.isChecked():
            vpc_env = "prod"
        elif self.vpc_test_radio.isChecked():
            vpc_env = "test"
        return {
            "vpc_env": vpc_env,
            "subnet_type": self.subnet_combo.currentData(),
            "rules": self._rules.copy(),
        }
    
    def set_data(self, data: dict):
        """
        Populate the page with existing data.
        
        Args:
            data: Dict with network section data
        """
        vpc_env = data.get("vpc_env")
        if not vpc_env:
            vpc_mode = data.get("vpc_mode")
            vpc_env = "prod" if vpc_mode == "default" else "dev"

        if vpc_env == "prod":
            self.vpc_prod_radio.setChecked(True)
        elif vpc_env == "test":
            self.vpc_test_radio.setChecked(True)
        else:
            self.vpc_dev_radio.setChecked(True)
        
        if "subnet_type" in data:
            for i in range(self.subnet_combo.count()):
                if self.subnet_combo.itemData(i) == data["subnet_type"]:
                    self.subnet_combo.setCurrentIndex(i)
                    break
        
        if "rules" in data:
            self._rules = data["rules"].copy()
            self._refresh_rules_table()
