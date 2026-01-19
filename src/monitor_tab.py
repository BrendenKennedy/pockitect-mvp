"""
Resource Monitor Tab

Displays a real-time view of all AWS resources across regions.
"""

import uuid
from typing import List, Dict, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTreeWidget, QTreeWidgetItem, QProgressBar, QLabel,
    QHeaderView, QMessageBox, QSplitter, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from app.core.aws.scanner import ScannedResource
from app.core.redis_client import RedisClient
from monitor_service import ResourceMonitoringService

class ResourceMonitorWidget(QWidget):
    """Main widget for the Monitor tab."""
    
    # Signal emitted when scan completes (for refreshing project status)
    scan_completed = Signal(list)
    
    def __init__(self, monitor_service: ResourceMonitoringService, parent=None):
        super().__init__(parent)
        self.monitor_service = monitor_service
        self._setup_ui()
        self.resources: List[ScannedResource] = []
        self.redis = RedisClient()
        self._delete_request_id = None
        self._delete_errors: List[str] = []
        self._delete_success_ids: List[str] = []
        self.pending_delete_items: List[QTreeWidgetItem] = []
        
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
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: white;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 24px;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        top_bar.addWidget(self.scan_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; 
                color: white;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 24px;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.delete_btn.setEnabled(False) # Default disabled
        top_bar.addWidget(self.delete_btn)
        
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
        
        # Left: Resource Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Region / Type / Resource", "ID", "State", "Name"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.itemClicked.connect(self._on_item_clicked)
        # Handle selection change for button state
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.tree)
        
        # Right: Details View
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Select a resource to view details...")
        splitter.addWidget(self.details_text)
        
        # Set splitter ratio (70% tree, 30% details)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        
    def start_scan(self):
        """Start the background scan."""
        self.scan_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Starting scan...")
        self.tree.clear()
        self.details_text.clear()
        
        # Request full scan
        self.monitor_service.request_scan(regions=None)
        
    def _update_status(self, msg):
        self.status_label.setText(msg)
        
    def _on_scan_finished(self, resources: List[ScannedResource]):
        self.resources = resources
        self.tree.clear()
        self._populate_tree(resources)
        
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

    def _populate_tree(self, resources: List[ScannedResource]):
        """Group resources by Region -> Type and populate the tree."""
        # Group data
        by_region = {}
        for r in resources:
            if r.region not in by_region:
                by_region[r.region] = {}
            
            if r.type not in by_region[r.region]:
                by_region[r.region][r.type] = []
                
            by_region[r.region][r.type].append(r)
            
        # Build tree
        for region in sorted(by_region.keys()):
            region_item = QTreeWidgetItem(self.tree)
            region_item.setText(0, region)
            region_item.setExpanded(True)
            
            # Region icon/color
            region_item.setForeground(0, QBrush(QColor("#3498db"))) # Blue
            
            types_in_region = by_region[region]
            for r_type in sorted(types_in_region.keys()):
                type_item = QTreeWidgetItem(region_item)
                type_item.setText(0, r_type)
                type_item.setExpanded(True)
                
                for res in types_in_region[r_type]:
                    item = QTreeWidgetItem(type_item)
                    
                    # Columns: Name/ID combo, ID, State, Name
                    display_name = res.name or res.id
                    item.setText(0, display_name)
                    item.setText(1, res.id)
                    item.setText(2, res.state)
                    item.setText(3, res.name or "-")
                    
                    # Color code state
                    if res.state in ['running', 'available', 'active', 'associated']:
                        item.setForeground(2, QBrush(QColor("#2ecc71"))) # Green
                    elif res.state in ['stopped', 'terminated']:
                        item.setForeground(2, QBrush(QColor("#e74c3c"))) # Red
                    else:
                        item.setForeground(2, QBrush(QColor("#f1c40f"))) # Yellow
                        
                    # Store reference to full object
                    item.setData(0, Qt.ItemDataRole.UserRole, res)

    def _on_selection_changed(self):
        """Update delete button based on selection."""
        items = self.tree.selectedItems()
        has_resources = False
        for item in items:
            if isinstance(item.data(0, Qt.ItemDataRole.UserRole), ScannedResource):
                has_resources = True
                break
        self.delete_btn.setEnabled(has_resources)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Show details when a resource is clicked."""
        # Note: _on_selection_changed handles the button enablement now,
        # but we still need to show details for the *clicked* (last) item.
        
        resource = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(resource, ScannedResource):
            # ... details logic ...
            details = f"Type: {resource.type}\n"
            details += f"ID: {resource.id}\n"
            details += f"Region: {resource.region}\n"
            details += f"Name: {resource.name}\n"
            details += f"State: {resource.state}\n\n"
            
            details += "--- Details ---\n"
            for k, v in resource.details.items():
                details += f"{k}: {v}\n"
                
            details += "\n--- Tags ---\n"
            for k, v in resource.tags.items():
                details += f"{k}: {v}\n"
                
            self.details_text.setText(details)
        else:
            self.details_text.clear()

    def delete_selected(self):
        """Delete the selected resources."""
        items = self.tree.selectedItems()
        if not items:
            return
            
        resources_to_delete = []
        for item in items:
            res = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(res, ScannedResource):
                resources_to_delete.append(res)
        
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
            
            self.pending_delete_items = items
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
            items_to_remove = []
            for item in self.pending_delete_items:
                res = item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(res, ScannedResource) and res.id in self._delete_success_ids:
                    items_to_remove.append(item)

            for item in items_to_remove:
                parent = item.parent()
                if parent:
                    parent.removeChild(item)

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

        self.pending_delete_items = []
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
