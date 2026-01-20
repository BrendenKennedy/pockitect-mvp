"""
Resource Monitor Tab

Displays a real-time view of all AWS resources across regions.
"""

import uuid
import html
from typing import List, Dict, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
    QLabel,
    QMessageBox,
    QSplitter,
    QScrollArea,
    QFrame,
    QGridLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from app.core.aws.scanner import ScannedResource
from app.core.redis_client import RedisClient
from monitor_service import ResourceMonitoringService
from storage import get_preference
from styles import ThemeManager


def _get_theme_colors() -> Dict[str, str]:
    theme_name = get_preference("theme", "modern_dark")
    return ThemeManager.get_colors(theme_name)


class _DashboardCard(QFrame):
    def __init__(self, colors: Dict[str, str], parent=None):
        super().__init__(parent)
        self.setObjectName("dashboardCard")
        self.setStyleSheet(
            f"""
            QFrame#dashboardCard {{
                background-color: {colors['bg_secondary']};
                border: 1px solid {colors['border_secondary']};
                border-radius: 12px;
            }}
            """
        )


class SummaryCard(_DashboardCard):
    def __init__(self, title: str, value: str, colors: Dict[str, str], parent=None):
        super().__init__(colors, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {colors['text_secondary']}; font-size: 12px;"
        )
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"color: {colors['text_primary']}; font-size: 20px; font-weight: bold;"
        )

        layout.addWidget(title_label)
        layout.addWidget(value_label)


class ResourceTypeCard(_DashboardCard):
    def __init__(self, resource_type: str, total: int, breakdown: Dict[str, int], colors: Dict[str, str], parent=None):
        super().__init__(colors, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title_label = QLabel(resource_type)
        title_label.setStyleSheet(
            f"color: {colors['text_primary']}; font-size: 14px; font-weight: bold;"
        )
        total_label = QLabel(f"Total: {total}")
        total_label.setStyleSheet(
            f"color: {colors['text_secondary']}; font-size: 12px;"
        )

        breakdown_label = QLabel(", ".join(f"{k}: {v}" for k, v in breakdown.items()) or "No data")
        breakdown_label.setStyleSheet(
            f"color: {colors['text_secondary']}; font-size: 11px;"
        )
        breakdown_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(total_label)
        layout.addWidget(breakdown_label)


class RegionCard(_DashboardCard):
    def __init__(self, region: str, total: int, breakdown: Dict[str, int], colors: Dict[str, str], parent=None):
        super().__init__(colors, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title_label = QLabel(region)
        title_label.setStyleSheet(
            f"color: {colors['text_primary']}; font-size: 14px; font-weight: bold;"
        )
        total_label = QLabel(f"Resources: {total}")
        total_label.setStyleSheet(
            f"color: {colors['text_secondary']}; font-size: 12px;"
        )

        breakdown_items = sorted(breakdown.items(), key=lambda item: item[1], reverse=True)[:4]
        breakdown_label = QLabel(", ".join(f"{k}: {v}" for k, v in breakdown_items) or "No data")
        breakdown_label.setStyleSheet(
            f"color: {colors['text_secondary']}; font-size: 11px;"
        )
        breakdown_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(total_label)
        layout.addWidget(breakdown_label)


class TextCard(_DashboardCard):
    def __init__(self, title: str, colors: Dict[str, str], parent=None):
        super().__init__(colors, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"color: {colors['text_secondary']}; font-size: 13px; font-weight: bold;"
        )
        self._body_label = QLabel("No data")
        self._body_label.setStyleSheet(
            f"color: {colors['text_primary']}; font-size: 12px;"
        )
        self._body_label.setWordWrap(True)

        layout.addWidget(self._title_label)
        layout.addWidget(self._body_label)

    def set_body(self, html_text: str) -> None:
        self._body_label.setText(html_text)
class ResourceMonitorWidget(QWidget):
    """Main widget for the Monitor tab."""
    
    # Signal emitted when scan completes (for refreshing project status)
    scan_completed = Signal(list)
    
    def __init__(self, monitor_service: ResourceMonitoringService, parent=None):
        super().__init__(parent)
        self.monitor_service = monitor_service
        self._colors = _get_theme_colors()
        self._setup_ui()
        self.resources: List[ScannedResource] = []
        self.redis = RedisClient()
        self._delete_request_id = None
        self._delete_errors: List[str] = []
        self._delete_success_ids: List[str] = []
        self.pending_delete_resources: List[ScannedResource] = []
        self._show_service_roles = False
        
        # Connect service signals
        self.monitor_service.scan_completed.connect(self._on_scan_finished)
        self.monitor_service.scan_progress.connect(self._update_status)
        self.monitor_service.scan_error.connect(self._on_scan_error)
        self.monitor_service.status_event.connect(self._on_status_event)
        
        # Auto-refresh disabled; scans are manual or event-driven.
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Top Bar ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(5, 5, 5, 5)  # Tight margins
        top_bar.setSpacing(8)
        
        self.scan_btn = QPushButton("Scan Project Regions")
        self.scan_btn.clicked.connect(self.start_scan)
        # Styling handled by global theme
        top_bar.addWidget(self.scan_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setProperty("danger", "true")  # Use danger button style from theme
        # Styling handled by global theme
        self.delete_btn.setEnabled(False) # Default disabled
        top_bar.addWidget(self.delete_btn)

        self.show_roles_checkbox = QCheckBox("Show AWS Service Roles")
        self.show_roles_checkbox.setChecked(False)
        self.show_roles_checkbox.stateChanged.connect(self._on_service_role_toggle)
        top_bar.addWidget(self.show_roles_checkbox)
        
        self.status_label = QLabel("Ready")
        self.status_label.setMinimumWidth(150)
        self.status_label.setMaximumHeight(24)
        top_bar.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setMaximumHeight(20)  # Compact height
        top_bar.addWidget(self.progress_bar)
        
        top_bar.addStretch()
        
        layout.addLayout(top_bar)
        
        # --- Main Content (Splitter) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Resource tree list
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Region / Type / Resource", "ID", "State", "Name"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.tree)

        # Right: Cards panel
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cards_scroll.setMinimumWidth(300)  # Ensure cards panel has minimum width
        self.cards_scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(8, 8, 8, 8)
        self.cards_layout.setSpacing(12)

        self.selected_card = TextCard("Selected Resource", self._colors)
        self.details_card = TextCard("Details", self._colors)
        self.tags_card = TextCard("Tags", self._colors)
        self.cards_layout.addWidget(self.selected_card)
        self.cards_layout.addWidget(self.details_card)
        self.cards_layout.addWidget(self.tags_card)

        # Summary section
        self.summary_section = QWidget()
        self.summary_layout = QGridLayout(self.summary_section)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setHorizontalSpacing(12)
        self.summary_layout.setVerticalSpacing(12)
        self.cards_layout.addWidget(self.summary_section)

        # Resource type section
        self.type_section = QWidget()
        self.type_layout = QGridLayout(self.type_section)
        self.type_layout.setContentsMargins(0, 0, 0, 0)
        self.type_layout.setHorizontalSpacing(12)
        self.type_layout.setVerticalSpacing(12)
        self.cards_layout.addWidget(self.type_section)

        # Region section
        self.region_section = QWidget()
        self.region_layout = QGridLayout(self.region_section)
        self.region_layout.setContentsMargins(0, 0, 0, 0)
        self.region_layout.setHorizontalSpacing(12)
        self.region_layout.setVerticalSpacing(12)
        self.cards_layout.addWidget(self.region_section)

        self.cards_layout.addStretch()
        self.cards_scroll.setWidget(self.cards_container)
        splitter.addWidget(self.cards_scroll)

        # Set splitter ratio (70% list, 30% cards)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        
    def start_scan(self):
        """Start the background scan."""
        self.scan_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Starting scan...")
        self.tree.clear()
        self._clear_detail_cards()
        
        # Request full scan
        self.monitor_service.request_scan(regions=None)
        
    def _update_status(self, msg):
        self.status_label.setText(msg)
        
    def _on_scan_finished(self, resources: List[ScannedResource]):
        self.resources = resources
        self._refresh_dashboard()
        
        self.scan_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Streaming update. Total {len(resources)} resources.")
        
        # Emit signal for project list to refresh status
        self.scan_completed.emit(resources)
        
        # Auto-refresh disabled
        
    def _on_scan_error(self, error_msg):
        self.scan_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Scan failed")
        QMessageBox.critical(self, "Scan Error", f"An error occurred:\n{error_msg}")

    def _refresh_dashboard(self):
        resources = self._filtered_resources()
        self._populate_tree(resources)
        self._populate_summary_cards(resources)
        self._populate_type_cards(resources)
        self._populate_region_cards(resources)
        if not self._get_selected_resources():
            self._clear_detail_cards()

    def _populate_summary_cards(self, resources: List[ScannedResource]) -> None:
        self._clear_layout(self.summary_layout)

        total = len(resources)
        by_type = {}
        by_region = {}
        for res in resources:
            by_type[res.type] = by_type.get(res.type, 0) + 1
            by_region[res.region] = by_region.get(res.region, 0) + 1

        cards = [
            SummaryCard("Total Resources", str(total), self._colors),
            SummaryCard("Resource Types", str(len(by_type)), self._colors),
            SummaryCard("Regions", str(len(by_region)), self._colors),
        ]

        for idx, card in enumerate(cards):
            self.summary_layout.addWidget(card, 0, idx)

    def _populate_type_cards(self, resources: List[ScannedResource]) -> None:
        self._clear_layout(self.type_layout)

        by_type: Dict[str, List[ScannedResource]] = {}
        for res in resources:
            by_type.setdefault(res.type, []).append(res)

        row = 0
        col = 0
        for resource_type in sorted(by_type.keys()):
            items = by_type[resource_type]
            breakdown = {}
            for res in items:
                state = res.state or "unknown"
                breakdown[state] = breakdown.get(state, 0) + 1
            card = ResourceTypeCard(resource_type, len(items), breakdown, self._colors)
            self.type_layout.addWidget(card, row, col)
            col += 1
            if col >= 3:
                row += 1
                col = 0

    def _populate_region_cards(self, resources: List[ScannedResource]) -> None:
        self._clear_layout(self.region_layout)

        by_region: Dict[str, List[ScannedResource]] = {}
        for res in resources:
            by_region.setdefault(res.region, []).append(res)

        row = 0
        col = 0
        for region in sorted(by_region.keys()):
            items = by_region[region]
            breakdown = {}
            for res in items:
                breakdown[res.type] = breakdown.get(res.type, 0) + 1
            card = RegionCard(region, len(items), breakdown, self._colors)
            self.region_layout.addWidget(card, row, col)
            col += 1
            if col >= 3:
                row += 1
                col = 0

    def _populate_tree(self, resources: List[ScannedResource]) -> None:
        self.tree.clear()
        by_region: Dict[str, Dict[str, List[ScannedResource]]] = {}
        for res in resources:
            by_region.setdefault(res.region, {}).setdefault(res.type, []).append(res)

        for region in sorted(by_region.keys()):
            region_item = QTreeWidgetItem(self.tree)
            region_item.setText(0, region)
            region_item.setExpanded(True)
            region_item.setForeground(0, QBrush(QColor(self._colors["status_info"])))

            types_in_region = by_region[region]
            for r_type in sorted(types_in_region.keys()):
                type_item = QTreeWidgetItem(region_item)
                type_item.setText(0, r_type)
                type_item.setExpanded(True)

                for res in types_in_region[r_type]:
                    item = QTreeWidgetItem(type_item)
                    display_name = res.name or res.id
                    item.setText(0, display_name)
                    item.setText(1, res.id)
                    item.setText(2, res.state or "-")
                    item.setText(3, res.name or "-")

                    if res.state in ['running', 'available', 'active', 'associated']:
                        item.setForeground(2, QBrush(QColor(self._colors["status_ok"])))
                    elif res.state in ['stopped', 'terminated']:
                        item.setForeground(2, QBrush(QColor(self._colors["status_error"])))
                    else:
                        item.setForeground(2, QBrush(QColor(self._colors["status_warning"])))

                    item.setData(0, Qt.ItemDataRole.UserRole, res)

    def _on_selection_changed(self) -> None:
        selected_resources = self._get_selected_resources()
        self.delete_btn.setEnabled(bool(selected_resources))
        if len(selected_resources) == 1:
            self._render_details(selected_resources[0])
        else:
            self._clear_detail_cards()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        resource = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(resource, ScannedResource):
            self._render_details(resource)

    def _render_details(self, resource: ScannedResource) -> None:
        details = dict(resource.details or {})
        arn = details.pop("arn", None)
        overview_lines = [
            f"<b>Type:</b> {html.escape(resource.type)}",
            f"<b>ID:</b> {html.escape(resource.id)}",
            f"<b>Region:</b> {html.escape(resource.region)}",
            f"<b>Name:</b> {html.escape(resource.name or '-')}",
            f"<b>State:</b> {html.escape(resource.state or '-')}",
        ]
        if arn:
            overview_lines.append(f"<b>ARN:</b> {html.escape(str(arn))}")
        self.selected_card.set_body("<br>".join(overview_lines))

        detail_rows = "<br>".join(
            f"<b>{html.escape(str(k))}:</b> {html.escape(str(v))}"
            for k, v in details.items()
        )
        self.details_card.set_body(detail_rows or "None")

        tag_rows = "<br>".join(
            f"<b>{html.escape(str(k))}:</b> {html.escape(str(v))}"
            for k, v in (resource.tags or {}).items()
        )
        self.tags_card.set_body(tag_rows or "None")

    def _clear_detail_cards(self) -> None:
        self.selected_card.set_body("Select a single resource to view details.")
        self.details_card.set_body("None")
        self.tags_card.set_body("None")

    def _get_selected_resources(self) -> List[ScannedResource]:
        selected = []
        for item in self.tree.selectedItems():
            res = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(res, ScannedResource):
                selected.append(res)
        return selected

    def _clear_layout(self, layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _is_service_role(self, resource: ScannedResource) -> bool:
        if resource.type != "iam_role":
            return False
        role_name = resource.id or ""
        arn = (resource.details or {}).get("arn", "")
        return role_name.startswith("AWSServiceRoleFor") or "/aws-service-role/" in arn

    def _filtered_resources(self) -> List[ScannedResource]:
        if self._show_service_roles:
            return self.resources
        return [res for res in self.resources if not self._is_service_role(res)]

    def _on_service_role_toggle(self) -> None:
        self._show_service_roles = self.show_roles_checkbox.isChecked()
        self._refresh_dashboard()

    def delete_selected(self):
        """Delete the selected resources."""
        resources_to_delete = self._get_selected_resources()
        if not resources_to_delete:
            return

        # Confirmation dialog
        msg = f"Are you sure you want to PERMANENTLY delete {len(resources_to_delete)} resource(s)?\n\n"
        if len(resources_to_delete) <= 5:
             for r in resources_to_delete:
                 msg += f"- {r.type} {r.id} ({r.region})\n"
        else:
            msg += f"- {resources_to_delete[0].type} {resources_to_delete[0].id} ... and {len(resources_to_delete)-1} others\n"
        
        msg += "\nThis action cannot be undone."

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText(f"Deleting {len(resources_to_delete)} resources...")
            self.scan_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.tree.setEnabled(False)
            
            self.pending_delete_resources = resources_to_delete
            self._delete_request_id = uuid.uuid4().hex
            self._delete_errors = []
            self._delete_success_ids = []

            payload = [
                {
                    "id": r.id,
                    "type": r.type,
                    "region": r.region,
                    "tags": r.tags,
                    "details": r.details,
                }
                for r in resources_to_delete
            ]
            self.redis.publish_command(
                "terminate",
                {"resources": payload},
                request_id=self._delete_request_id,
            )

    def _on_status_event(self, event: dict):
        event_type = event.get("type")
        request_id = event.get("request_id")
        if self._delete_request_id and request_id and request_id != self._delete_request_id:
            return
        if event_type not in (
            "terminate_progress",
            "terminate_error",
            "terminate_skipped",
            "terminate_complete",
            "terminate_confirmed",
            "terminate_confirm_error",
        ):
            return

        if event_type == "terminate_progress":
            data = event.get("data", {})
            res_id = data.get("resource_id")
            if res_id:
                self._delete_success_ids.append(res_id)
            self.status_label.setText("Deleting resources...")
        elif event_type == "terminate_error":
            data = event.get("data", {})
            error = data.get("error", "Unknown error")
            res_id = data.get("resource_id")
            self._delete_errors.append(f"{res_id}: {error}")
        elif event_type == "terminate_skipped":
            data = event.get("data", {})
            res_id = data.get("resource_id")
            reason = data.get("reason", "Skipped")
            self._delete_errors.append(f"{res_id}: {reason}")
        elif event_type == "terminate_complete":
            self.status_label.setText("Deletion completed. Confirming...")
        elif event_type == "terminate_confirmed":
            payload = event.get("data", {}) or {}
            confirmed_ids = payload.get("confirmed_ids") or []
            shared_ids = payload.get("shared_ids") or []
            self._delete_success_ids.extend([rid for rid in confirmed_ids + shared_ids if rid])
            self._finish_delete_flow()
        elif event_type == "terminate_confirm_error":
            payload = event.get("data", {}) or {}
            failed_ids = payload.get("failed_ids") or []
            confirm_errors = payload.get("errors") or []
            for res_id in failed_ids:
                self._delete_errors.append(f"{res_id}: confirmation failed")
            self._delete_errors.extend([str(err) for err in confirm_errors])
            self._finish_delete_flow()

    def _finish_delete_flow(self):
        self.scan_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.tree.setEnabled(True)

        if self._delete_success_ids:
            remaining = [
                res for res in self.resources
                if res.id not in self._delete_success_ids
            ]
            self.resources = remaining
            self._refresh_dashboard()

        if not self._delete_errors:
            self.status_label.setText("Deletion complete.")
            QMessageBox.information(self, "Success", f"Successfully deleted {len(self._delete_success_ids)} resources.")
        else:
            self.status_label.setText("Deletion complete with errors.")
            error_msg = "\n".join(self._delete_errors[:10])
            if len(self._delete_errors) > 10:
                error_msg += f"\n...and {len(self._delete_errors)-10} more."
            QMessageBox.warning(self, "Partial Success", 
                f"Deleted {len(self._delete_success_ids)} resources.\n\nErrors:\n{error_msg}")

        self.pending_delete_resources = []
        self._delete_request_id = None
    
    def get_resources_by_project(self, project_name: str) -> List[ScannedResource]:
        """Get all scanned resources for a given project name (based on tags or naming)."""
        matching = []
        for res in self.resources:
            # Check tags for pockitect:project
            if 'pockitect:project' in res.tags:
                if res.tags['pockitect:project'] == project_name:
                    matching.append(res)
            # Also check if name starts with project name (fallback)
            elif res.name and res.name.startswith(project_name):
                matching.append(res)
        return matching
