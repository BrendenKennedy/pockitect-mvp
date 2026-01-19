"""
Wizard Page 2: Compute Configuration

Collects:
- Instance type (filtered by region quota - future)
- OS image / AMI
- User data script (optional)
"""

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QComboBox, QTextEdit, 
    QFormLayout, QVBoxLayout, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt

from ..base import StyledWizardPage, create_info_label

# Common instance types for MVP
INSTANCE_TYPES = [
    ("t3.micro", "t3.micro - 2 vCPU, 1 GB RAM (Free tier eligible)"),
    ("t3.small", "t3.small - 2 vCPU, 2 GB RAM"),
    ("t3.medium", "t3.medium - 2 vCPU, 4 GB RAM"),
    ("t3.large", "t3.large - 2 vCPU, 8 GB RAM"),
    ("t3.xlarge", "t3.xlarge - 4 vCPU, 16 GB RAM"),
    ("m5.large", "m5.large - 2 vCPU, 8 GB RAM (General purpose)"),
    ("m5.xlarge", "m5.xlarge - 4 vCPU, 16 GB RAM"),
    ("c5.large", "c5.large - 2 vCPU, 4 GB RAM (Compute optimized)"),
    ("r5.large", "r5.large - 2 vCPU, 16 GB RAM (Memory optimized)"),
]

# Common AMIs (these would be fetched dynamically in production)
# Format: (ami_id_placeholder, display_name, description)
COMMON_AMIS = [
    ("amazon-linux-2023", "Amazon Linux 2023", "Latest Amazon Linux with long-term support"),
    ("ubuntu-22.04", "Ubuntu 22.04 LTS", "Popular Linux distribution"),
    ("ubuntu-24.04", "Ubuntu 24.04 LTS", "Latest Ubuntu LTS release"),
    ("debian-12", "Debian 12", "Stable Debian release"),
    ("windows-2022", "Windows Server 2022", "Latest Windows Server"),
    ("custom", "Custom AMI ID", "Enter your own AMI ID"),
]

# User data templates
USER_DATA_TEMPLATES = {
    "none": "",
    "nginx": """#!/bin/bash
apt update
apt install -y nginx
systemctl enable nginx
systemctl start nginx
echo "<h1>Hello from Pockitect!</h1>" > /var/www/html/index.html
""",
    "docker": """#!/bin/bash
apt update
apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
apt update
apt install -y docker-ce docker-ce-cli containerd.io
systemctl enable docker
systemctl start docker
""",
    "node": """#!/bin/bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g pm2
""",
}


class ComputePage(StyledWizardPage):
    """
    Second wizard page: configure EC2 instance.
    """
    
    def __init__(self, parent=None):
        super().__init__(
            title="Compute",
            subtitle="Configure your EC2 instance type, operating system, and startup script.",
            parent=parent
        )
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Build the UI components."""
        # Instance type section
        form = self.add_form_section("Instance Configuration")
        
        self.instance_type_combo = QComboBox()
        self.instance_type_combo.setMinimumHeight(32)
        for type_id, type_name in INSTANCE_TYPES:
            self.instance_type_combo.addItem(type_name, type_id)
        form.addRow("Instance Type:", self.instance_type_combo)
        
        info = create_info_label(
            "t3.micro is free tier eligible for up to 750 hours/month. "
            "Choose based on your workload requirements."
        )
        form.addRow("", info)
        
        # AMI section
        ami_form = self.add_form_section("Operating System")
        
        self.ami_combo = QComboBox()
        self.ami_combo.setMinimumHeight(32)
        for ami_id, ami_name, ami_desc in COMMON_AMIS:
            self.ami_combo.addItem(f"{ami_name} - {ami_desc}", ami_id)
        ami_form.addRow("Image:", self.ami_combo)
        
        # Custom AMI input (hidden by default)
        self.custom_ami_edit = QLineEdit()
        self.custom_ami_edit.setPlaceholderText("ami-0123456789abcdef0")
        self.custom_ami_edit.setMinimumHeight(32)
        self.custom_ami_edit.setVisible(False)
        self.custom_ami_label = QLabel("Custom AMI ID:")
        self.custom_ami_label.setVisible(False)
        ami_form.addRow(self.custom_ami_label, self.custom_ami_edit)
        
        # User data section
        ud_section = self.add_section("Startup Script (User Data)")
        
        # Template selector
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Quick template:"))
        
        self.template_combo = QComboBox()
        self.template_combo.addItem("None", "none")
        self.template_combo.addItem("Nginx Web Server", "nginx")
        self.template_combo.addItem("Docker", "docker")
        self.template_combo.addItem("Node.js", "node")
        template_layout.addWidget(self.template_combo)
        template_layout.addStretch()
        ud_section.addLayout(template_layout)
        
        self.user_data_edit = QTextEdit()
        self.user_data_edit.setPlaceholderText(
            "#!/bin/bash\n# Enter commands to run when the instance starts...\n"
        )
        self.user_data_edit.setMinimumHeight(150)
        self.user_data_edit.setStyleSheet("font-family: monospace;")
        ud_section.addWidget(self.user_data_edit)
        
        info2 = create_info_label(
            "User data scripts run as root when the instance first boots. "
            "Use them to install packages, configure services, or download your application."
        )
        ud_section.addWidget(info2)
        
        # Register fields
        self.registerField("instance_type", self.instance_type_combo, "currentData")
        self.registerField("custom_ami", self.custom_ami_edit)
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.ami_combo.currentIndexChanged.connect(self._on_ami_changed)
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
    
    def _on_ami_changed(self, index: int):
        """Show/hide custom AMI input based on selection."""
        ami_id = self.ami_combo.currentData()
        is_custom = (ami_id == "custom")
        self.custom_ami_edit.setVisible(is_custom)
        self.custom_ami_label.setVisible(is_custom)
    
    def _on_template_changed(self, index: int):
        """Apply selected user data template."""
        template_key = self.template_combo.currentData()
        if template_key in USER_DATA_TEMPLATES:
            self.user_data_edit.setPlainText(USER_DATA_TEMPLATES[template_key])
    
    def get_data(self) -> dict:
        """
        Get the collected data from this page.
        
        Returns:
            Dict with compute section data
        """
        ami_selection = self.ami_combo.currentData()
        
        # For custom AMI, use the text input; otherwise use placeholder
        # In production, these would be resolved to actual AMI IDs
        if ami_selection == "custom":
            image_id = self.custom_ami_edit.text().strip()
        else:
            # Placeholder - would be resolved to actual AMI ID for region
            image_id = ami_selection
        
        return {
            "instance_type": self.instance_type_combo.currentData(),
            "image_id": image_id,
            "image_name": self.ami_combo.currentText().split(" - ")[0],
            "user_data": self.user_data_edit.toPlainText(),
        }
    
    def set_data(self, data: dict):
        """
        Populate the page with existing data.
        
        Args:
            data: Dict with compute section data
        """
        if "instance_type" in data:
            for i in range(self.instance_type_combo.count()):
                if self.instance_type_combo.itemData(i) == data["instance_type"]:
                    self.instance_type_combo.setCurrentIndex(i)
                    break
        
        if "image_id" in data:
            image_id = data["image_id"]
            found = False
            for i in range(self.ami_combo.count()):
                if self.ami_combo.itemData(i) == image_id:
                    self.ami_combo.setCurrentIndex(i)
                    found = True
                    break
            if not found and image_id:
                # It's a custom AMI
                for i in range(self.ami_combo.count()):
                    if self.ami_combo.itemData(i) == "custom":
                        self.ami_combo.setCurrentIndex(i)
                        self.custom_ami_edit.setText(image_id)
                        break
        
        if "user_data" in data:
            self.user_data_edit.setPlainText(data["user_data"])
