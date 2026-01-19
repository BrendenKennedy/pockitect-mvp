from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QMessageBox,
    QGridLayout,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

STATUS_COLORS = {
    "pending": "#6c7086",
    "creating": "#89b4fa",
    "created": "#a6e3a1",
    "running": "#a6e3a1",
    "stopped": "#f9e2af",
    "terminating": "#f38ba8",
    "deleted": "#6c7086",
    "failed": "#f38ba8",
}

# SVG icon definitions - using COLOR_PLACEHOLDER for dynamic coloring
COLOR_PLACEHOLDER = "{{COLOR}}"

PENCIL_ICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{COLOR_PLACEHOLDER}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
</svg>"""

CLOUD_ICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{COLOR_PLACEHOLDER}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path>
  <path d="M12 16v-4"></path>
  <path d="M10 14l2-2 2 2"></path>
</svg>"""

PLAY_ICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{COLOR_PLACEHOLDER}">
  <path d="M8 5v14l11-7z"></path>
</svg>"""

STOP_ICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{COLOR_PLACEHOLDER}">
  <rect x="6" y="6" width="12" height="12" rx="1"></rect>
</svg>"""

TRASH_ICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{COLOR_PLACEHOLDER}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="3 6 5 6 21 6"></polyline>
  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
  <line x1="10" y1="11" x2="10" y2="17"></line>
  <line x1="14" y1="11" x2="14" y2="17"></line>
</svg>"""

CLOSE_ICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{COLOR_PLACEHOLDER}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="18" y1="6" x2="6" y2="18"></line>
  <line x1="6" y1="6" x2="18" y2="18"></line>
</svg>"""


def create_icon_from_svg(svg_data: str, color: str = "#cdd6f4", size: int = 20) -> QIcon:
    """Create a QIcon from SVG data with a specific color."""
    renderer = QSvgRenderer()
    # Replace COLOR_PLACEHOLDER with the actual color
    colored_svg = svg_data.replace(COLOR_PLACEHOLDER, color)
    
    if not renderer.load(colored_svg.encode('utf-8')):
        # Fallback: try with a simple replacement
        fallback_svg = svg_data.replace(COLOR_PLACEHOLDER, color)
        renderer.load(fallback_svg.encode('utf-8'))
    
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    
    icon = QIcon(pixmap)
    return icon


def create_icon_button(svg_data: str, tooltip: str, color: str, hover_color: str, 
                       bg_color: str = "transparent", hover_bg: str = None, 
                       size: int = 32) -> QPushButton:
    """Create a button with an SVG icon."""
    btn = QPushButton()
    btn.setFixedSize(size, size)
    btn.setIcon(create_icon_from_svg(svg_data, color, 18))
    btn.setIconSize(QSize(18, 18))
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    
    hover_bg = hover_bg or bg_color
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg_color};
            border: none;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
        }}
    """)
    
    return btn


class DeveloperInfoCard(QFrame):
    """A card showing useful developer information."""
    
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #cdd6f4; padding: 0px;")
        title_label.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title_label)
        
        # Content (supports plain text with newlines)
        self.content_label = QLabel(content)
        self.content_label.setStyleSheet("""
            font-size: 11px; 
            color: #a6adc8; 
            font-family: 'Courier New', monospace; 
            padding: 4px 0px;
        """)
        self.content_label.setWordWrap(True)
        self.content_label.setTextFormat(Qt.TextFormat.PlainText)
        self.content_label.setContentsMargins(0, 0, 0, 0)
        # Ensure minimum height for content to prevent cutoff
        self.content_label.setMinimumHeight(60)
        layout.addWidget(self.content_label)
        
        # Set minimum height for the card itself
        self.setMinimumHeight(100)
    
    def update_content(self, content: str):
        self.content_label.setText(content)


class ProjectRowWidget(QWidget):
    """Custom widget for a project row in the list."""

    # Signals for actions
    action_edit = Signal(str)      # slug
    action_monitor = Signal(str)   # project_name
    action_delete_file = Signal(str) # slug
    action_terminate = Signal(str) # project_name
    action_deploy = Signal(str)    # slug
    action_start = Signal(str)     # project_name
    action_stop = Signal(str)      # project_name
    view_toggled = Signal(str, bool)  # slug, expanded

    def __init__(
        self,
        project_data,
        resource_count=0,
        status="draft",
        blueprint=None,
        list_item=None,
        monitor_resources=None,
        expanded=False,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project_data
        self.slug = project_data.get("slug")
        self.name = project_data.get("name", "Unnamed")
        self.description = project_data.get("description", "")
        self.region = project_data.get("region", "us-east-1")
        # Get cost from project_data or blueprint
        self.cost = project_data.get("cost")
        if self.cost is None and blueprint:
            project_info = blueprint.get("project", {})
            self.cost = project_info.get("cost")
        self.resource_count = resource_count
        self.status = status  # "draft", "running", "stopped"
        self.blueprint = blueprint or {}
        self._expanded = expanded
        self._list_item = list_item
        self._monitor_resources = monitor_resources or []
        self._num_cards = 0  # Track number of info cards

        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(10)

        layout = QHBoxLayout()

        # Info Column
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)

        self._name_label = QLabel(self.name)
        self._name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4; padding: 0px;")
        self._name_label.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(self._name_label)

        self._meta_label = QLabel(self._build_meta_text())
        self._meta_label.setStyleSheet("color: #a6adc8; font-size: 12px; padding: 0px;")
        self._meta_label.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(self._meta_label)

        # Status Badge
        status_layout = QHBoxLayout()
        self._status_label = QLabel(f"● {self.status.upper()}")
        self._status_label.setStyleSheet(self._status_style())
        status_layout.addWidget(self._status_label)

        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self._update_count_label()
        status_layout.addWidget(self._count_label)

        status_layout.addStretch()
        info_layout.addLayout(status_layout)

        layout.addLayout(info_layout, stretch=1)

        # Actions Column
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(6)
        self._build_actions()
        layout.addLayout(self._actions_layout)
        root.addLayout(layout)

        self.details_frame = QFrame()
        self.details_frame.setVisible(self._expanded)
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(0, 15, 0, 0)
        details_layout.setSpacing(12)
        
        # Developer info cards grid
        self._info_grid = QGridLayout()
        self._info_grid.setSpacing(12)
        self._info_grid.setContentsMargins(0, 0, 0, 0)
        details_layout.addLayout(self._info_grid)

        root.addWidget(self.details_frame)

        self._build_developer_info_cards()
        
        # Set minimum size to ensure content isn't cut off
        self.setMinimumHeight(110 if not self._expanded else 200)
        
        if self._expanded and self._list_item:
            # Calculate proper size hint for expanded state
            hint = self.sizeHint()
            # Add extra height to prevent cutoff
            hint.setHeight(max(hint.height(), 250))
            self._list_item.setSizeHint(hint)

    def _build_meta_text(self) -> str:
        meta_text = f"Region: {self.region}"
        if self.cost is not None:
            cost_str = f"${self.cost:.2f}" if isinstance(self.cost, (int, float)) else str(self.cost)
            meta_text += f" | Cost: {cost_str}"
        if self.description:
            meta_text += f" | {self.description[:40]}"
            if len(self.description) > 40:
                meta_text += "..."
        return meta_text

    def _status_style(self) -> str:
        color = "#6c7086"  # Gray (draft)
        if self.status == "running":
            color = "#a6e3a1"
        elif self.status == "stopped":
            color = "#f9e2af"
        elif self.status == "deploying":
            color = "#89b4fa"
        elif self.status == "starting":
            color = "#89b4fa"
        elif self.status == "stopping":
            color = "#f9e2af"
        elif self.status == "terminating":
            color = "#f38ba8"
        elif self.status == "failed":
            color = "#f38ba8"
        return f"color: {color}; font-weight: bold; font-size: 11px;"

    def _update_count_label(self):
        if self.resource_count > 0:
            self._count_label.setText(f"({self.resource_count} resources)")
            self._count_label.setVisible(True)
        else:
            self._count_label.setText("")
            self._count_label.setVisible(False)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _build_actions(self):
        self._clear_layout(self._actions_layout)

        self.btn_edit = create_icon_button(
            PENCIL_ICON_SVG,
            "Edit Blueprint",
            "#89b4fa",
            "#74c7ec",
            bg_color="transparent",
            hover_bg="#313244",
        )
        self.btn_edit.clicked.connect(lambda: self.action_edit.emit(self.slug))
        self._actions_layout.addWidget(self.btn_edit)

        if self.status in ["draft", "failed"]:
            self.btn_deploy = create_icon_button(
                CLOUD_ICON_SVG,
                "Deploy infrastructure to AWS",
                "#a6e3a1",
                "#94e2d5",
                bg_color="transparent",
                hover_bg="#313244",
            )
            self.btn_deploy.clicked.connect(lambda: self.action_deploy.emit(self.slug))
            self._actions_layout.addWidget(self.btn_deploy)

        if self.status in ["running", "stopped", "starting", "stopping"]:
            is_running = self.status in ["running", "starting"]
            if is_running:
                self.btn_power = create_icon_button(
                    STOP_ICON_SVG,
                    "Stop Instances",
                    "#f38ba8",
                    "#eba0ac",
                    bg_color="transparent",
                    hover_bg="#313244",
                )
                self.btn_power.clicked.connect(lambda: self.action_stop.emit(self.name))
            else:
                self.btn_power = create_icon_button(
                    PLAY_ICON_SVG,
                    "Start Instances",
                    "#a6e3a1",
                    "#94e2d5",
                    bg_color="transparent",
                    hover_bg="#313244",
                )
                self.btn_power.clicked.connect(lambda: self.action_start.emit(self.name))
            self._actions_layout.addWidget(self.btn_power)

        if self.status in ["running", "stopped", "deploying", "terminating", "starting", "stopping"]:
            self.btn_terminate = create_icon_button(
                TRASH_ICON_SVG,
                "Terminate all resources",
                "#f38ba8",
                "#eba0ac",
                bg_color="transparent",
                hover_bg="#313244",
            )
            if self.status in ["terminating", "stopping"]:
                self.btn_terminate.setEnabled(False)
                self.btn_terminate.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        border-radius: 4px;
                        opacity: 0.5;
                    }
                """)
            self.btn_terminate.clicked.connect(self._confirm_terminate)
            self._actions_layout.addWidget(self.btn_terminate)

        self.btn_delete = create_icon_button(
            CLOSE_ICON_SVG,
            "Delete Blueprint File",
            "#6c7086",
            "#a6adc8",
            bg_color="transparent",
            hover_bg="#313244",
        )
        self.btn_delete.clicked.connect(self._confirm_delete_file)
        self._actions_layout.addWidget(self.btn_delete)

    def update_data(
        self,
        project_data,
        resource_count=0,
        status="draft",
        blueprint=None,
        monitor_resources=None,
    ):
        self.project = project_data
        self.slug = project_data.get("slug")
        self.name = project_data.get("name", "Unnamed")
        self.description = project_data.get("description", "")
        self.region = project_data.get("region", "us-east-1")
        # Get cost from project_data or blueprint
        self.cost = project_data.get("cost")
        if self.cost is None and blueprint:
            project_info = blueprint.get("project", {})
            self.cost = project_info.get("cost")
        self.resource_count = resource_count
        self.status = status
        self.blueprint = blueprint or {}
        self._monitor_resources = monitor_resources or []

        self._name_label.setText(self.name)
        self._meta_label.setText(self._build_meta_text())
        self._status_label.setText(f"● {self.status.upper()}")
        self._status_label.setStyleSheet(self._status_style())
        self._update_count_label()
        self._build_actions()

        if self._expanded:
            self._build_developer_info_cards()
            if self._list_item:
                rows = (self._num_cards + 1) // 2
                min_expanded_height = 110 + (rows * 115) + 40
                hint = QSize(self._list_item.sizeHint().width(), min_expanded_height)
                self._list_item.setSizeHint(hint)
        
    def _confirm_terminate(self):
        msg = f"Are you sure you want to TERMINATE project '{self.name}'?\n\n" \
              "This will recursively delete ALL tracked resources:\n" \
              "- EC2 Instances\n- VPCs\n- Load Balancers\n- Databases\n\n" \
              "This action cannot be undone."
              
        reply = QMessageBox.question(self, "Confirm Termination", msg, 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.action_terminate.emit(self.name)

    def _confirm_delete_file(self):
        msg = f"Delete blueprint file for '{self.name}'?"
        if self.status == "deployed":
            msg += "\n\nWARNING: This project is DEPLOYED. Deleting the file will NOT delete the AWS resources. " \
                   "Use 'Terminate' first if you want to clean up."
                   
        reply = QMessageBox.question(self, "Delete File", msg,
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.Yes:
            self.action_delete_file.emit(self.slug)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self.details_frame.setVisible(self._expanded)
        if self._list_item:
            # Recalculate size hint when expanding/collapsing
            if self._expanded:
                # Expanded: calculate based on number of cards
                rows = (self._num_cards + 1) // 2  # 2 columns
                # Estimate: base row (110px) + card rows (~110px each) + spacing
                min_expanded_height = 110 + (rows * 115) + 40
                hint = QSize(self._list_item.sizeHint().width(), min_expanded_height)
            else:
                # Collapsed: standard height
                hint = QSize(self._list_item.sizeHint().width(), 110)
            self._list_item.setSizeHint(hint)
        self.view_toggled.emit(self.slug, self._expanded)

    def mousePressEvent(self, event):
        clicked = self.childAt(event.position().toPoint())
        if isinstance(clicked, QPushButton):
            return super().mousePressEvent(event)
        self._toggle_expand()
        return super().mousePressEvent(event)

    def _build_developer_info_cards(self):
        """Build developer-friendly information cards from monitor data and blueprint."""
        # Clear existing cards properly to prevent double deletion
        for i in reversed(range(self._info_grid.count())):
            item = self._info_grid.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
        
        cards = []
        
        # Extract resource info from monitor data
        ec2_instance = None
        rds_instance = None
        load_balancer = None
        
        for res in self._monitor_resources:
            if res.type == "ec2_instance":
                ec2_instance = res
            elif res.type == "rds_instance":
                rds_instance = res
            elif res.type in ("elb", "alb", "nlb", "load_balancer"):
                load_balancer = res
        
        # SSH / Server Access Card
        if ec2_instance:
            public_ip = ec2_instance.details.get("public_ip") or "—"
            private_ip = ec2_instance.details.get("private_ip") or "—"
            instance_type = ec2_instance.details.get("type") or "—"
            state = ec2_instance.state or "unknown"
            
            # Check if SSH is accessible
            network = self.blueprint.get("network", {})
            ssh_open = self._is_sshable(network, public_ip)
            ssh_status = "✓ Port 22 OPEN" if ssh_open else "✗ Port 22 CLOSED"
            
            ssh_content = f"""Public IP: {public_ip}\n{ssh_status}\nPrivate IP: {private_ip}\nType: {instance_type}\nState: {state}"""
            
            cards.append(DeveloperInfoCard("🔐 SSH Access", ssh_content))
        
        # Database Card
        if rds_instance:
            db_details = rds_instance.details
            engine = db_details.get("engine") or "—"
            db_class = db_details.get("class") or "—"
            endpoint = db_details.get("endpoint") or "—"
            state = rds_instance.state or "unknown"
            
            db_content = f"""Endpoint: {endpoint}\nEngine: {engine}\nClass: {db_class}\nStatus: {state}"""
            
            cards.append(DeveloperInfoCard("🗄️ Database", db_content))
        
        # Load Balancer Card
        if load_balancer:
            lb_details = load_balancer.details
            dns_name = lb_details.get("dns_name") or lb_details.get("dns") or "—"
            state = load_balancer.state or "unknown"
            health_check = lb_details.get("health_check") or "—"
            
            lb_content = f"""DNS: {dns_name}\nStatus: {state}\nHealth Check: {health_check}"""
            
            cards.append(DeveloperInfoCard("⚖️ Load Balancer", lb_content))
        
        # S3 Bucket Card
        s3_resource = None
        for res in self._monitor_resources:
            if res.type == "s3_bucket":
                s3_resource = res
                break
        
        if s3_resource:
            bucket_name = s3_resource.name or s3_resource.id
            region = s3_resource.region or "global"
            
            s3_content = f"""Bucket: {bucket_name}\nRegion: {region}\nStatus: {s3_resource.state or 'active'}"""
            
            cards.append(DeveloperInfoCard("🪣 S3 Bucket", s3_content))
        
        # Network Info Card
        network = self.blueprint.get("network", {})
        vpc_env = network.get("vpc_env") or "—"
        vpc_id = network.get("vpc_id") or "—"
        
        # Try to get VPC from monitor resources
        vpc_resource = None
        for res in self._monitor_resources:
            if res.type == "vpc":
                vpc_resource = res
                break
        
        if vpc_resource:
            vpc_id = vpc_resource.id
            cidr = vpc_resource.details.get("cidr") or "—"
            vpc_content = f"""VPC: {vpc_id}\nEnvironment: {vpc_env}\nCIDR: {cidr}"""
        else:
            vpc_content = f"""VPC: {vpc_id}\nEnvironment: {vpc_env}"""
        
        cards.append(DeveloperInfoCard("🌐 Network", vpc_content))
        
        # Open Ports Card
        rules = network.get("rules", [])
        if rules:
            open_ports = sorted(set([str(r.get("port", "")) for r in rules if r.get("port")]))
            ports_text = ", ".join(open_ports[:10])
            if len(open_ports) > 10:
                ports_text += f" (+{len(open_ports) - 10} more)"
            
            ports_content = f"""Open Ports: {ports_text}\nTotal Rules: {len(rules)}"""
            
            cards.append(DeveloperInfoCard("🔓 Open Ports", ports_content))
        
        # Cost Card
        project_info = self.blueprint.get("project", {}) if self.blueprint else {}
        cost = self.cost if self.cost is not None else project_info.get("cost")
        if cost is not None:
            cost_str = f"${cost:.2f}" if isinstance(cost, (int, float)) else str(cost)
            cost_content = f"""Estimated Cost: {cost_str}\nPer Month"""
            cards.append(DeveloperInfoCard("💰 Cost", cost_content))
        
        # Add cards to grid (2 columns)
        self._num_cards = len(cards)
        row = 0
        col = 0
        for card in cards:
            self._info_grid.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

    def _build_quick_info(self) -> str:
        project = self.blueprint.get("project", {}) if self.blueprint else {}
        compute = self.blueprint.get("compute", {}) if self.blueprint else {}
        network = self.blueprint.get("network", {}) if self.blueprint else {}
        data = self.blueprint.get("data", {}) if self.blueprint else {}

        public_ip = compute.get("public_ip") or "—"
        private_ip = compute.get("private_ip") or "—"
        instance_type = compute.get("instance_type") or "—"
        sshable = self._is_sshable(network, public_ip)

        db = data.get("db", {}) if isinstance(data.get("db"), dict) else {}
        db_engine = db.get("engine") or "—"
        db_class = db.get("instance_class") or "—"
        db_endpoint = db.get("endpoint") or "—"

        s3 = data.get("s3_bucket", {}) if isinstance(data.get("s3_bucket"), dict) else {}
        s3_name = s3.get("name") or "—"

        lines = [
            f"Instance Type: {instance_type}",
            f"Public IP: {public_ip}",
            f"Private IP: {private_ip}",
            f"SSHable: {'yes' if sshable else 'no'}",
            f"DB: {db_engine} / {db_class} / {db_endpoint}",
            f"S3 Bucket: {s3_name}",
            f"VPC Env: {network.get('vpc_env') or '—'}",
            f"Region: {project.get('region') or self.region}",
        ]
        return "\n".join(lines)

    def _is_sshable(self, network: dict, public_ip: str) -> bool:
        if not public_ip or public_ip == "—":
            return False
        rules = network.get("rules") or []
        for rule in rules:
            if rule.get("port") == 22 and rule.get("cidr") in ("0.0.0.0/0", "::/0"):
                return True
        return False

