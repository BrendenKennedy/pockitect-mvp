#!/usr/bin/env python3
"""
Pockitect MVP - Main Application Entry Point

A desktop-first, local-first AWS infrastructure wizard.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Fix for WSL and Linux Qt issues
# On Windows, don't set QT_QPA_PLATFORM - let Qt auto-detect (uses 'windows' by default)
if 'QT_QPA_PLATFORM' not in os.environ:
    if sys.platform == 'win32':
        # Windows: Qt will auto-detect 'windows' platform plugin
        pass
    elif hasattr(os, 'uname'):
        # Linux/Unix: Check for WSL or use xcb
        is_wsl = 'microsoft' in os.uname().release.lower()
        if is_wsl:
            os.environ['QT_QPA_PLATFORM'] = 'wayland;xcb'
        else:
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
    else:
        # Fallback for other Unix-like systems
        os.environ['QT_QPA_PLATFORM'] = 'xcb'
        
os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '1')
os.environ.setdefault('QT_QPA_PLATFORMTHEME', '')


from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QFont


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import logging configuration
from app.core.config import setup_logging
from app.core.listeners import CommandListener
from app.core.confirmation_listener import ConfirmationListener
from app.core.aws.managed_vpc_service import ManagedVpcService, MANAGED_ENVS
from app.core.aws.scanner import ALL_REGIONS
from app.core.project_status import ProjectStatusCalculator
from app.core.utils import extract_regions_from_resources

from storage import (
    init_storage,
    list_projects,
    load_project,
    delete_project,
    save_project,
    get_workspace_root,
    DEFAULT_PROJECTS_DIR,
    write_project_regions_cache,
    get_preference,
)
from wizard.wizard import InfrastructureWizard
from template_selector_dialog import TemplateSelectorDialog
from watcher import ProjectWatcher
from styles import ThemeManager
from auth_dialog import AWSLoginDialog
from monitor_tab import ResourceMonitorWidget
from monitor_service import ResourceMonitoringService
from quotas_tab import QuotasTab
from status_event_service import StatusEventService
from project_row import ProjectRowWidget
from workers import DeleteWorker, PowerWorker
from deploy_worker import ProjectDeployWorker
from ai.agent_tab import AIAgentTab
import threading

# Setup Logging
logger = setup_logging(__name__)


class ProjectListWidget(QWidget):
    """Widget displaying the list of projects."""
    
    project_edit = Signal(str)
    project_monitor = Signal(str)
    
    def __init__(self, parent=None, monitor_tab=None):
        super().__init__(parent)
        self.monitor_tab = monitor_tab 
        self.project_status = {}
        self._rows_by_project = {}
        self._expanded_projects = set()
        self._ui_state_path = get_workspace_root() / "data" / "cache" / "ui_state.json"
        # Debounce timer to prevent rapid successive refreshes
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_refresh_projects)
        self._pending_refresh = False
        self._refreshing = False  # Guard to prevent concurrent refreshes
        self._pending_project_updates = set()
        self._row_update_timer = QTimer(self)
        self._row_update_timer.setSingleShot(True)
        self._row_update_timer.timeout.connect(self._apply_project_updates)
        self._load_ui_state()
        self._setup_ui()
        self._connect_signals()
        self.refresh_projects()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        title = QLabel("Projects")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        self.new_btn = QPushButton("+ New Project")
        self.new_btn.setObjectName("primaryButton")
        header.addWidget(self.new_btn)
        layout.addLayout(header)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget::item { border-bottom: 1px solid #333; }")
        layout.addWidget(self.list_widget)
        
        actions = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh List")
        actions.addWidget(self.refresh_btn)
        actions.addStretch()
        layout.addLayout(actions)
    
    def _connect_signals(self):
        self.refresh_btn.clicked.connect(self.refresh_projects)

    def handle_status_event(self, event: dict):
        event_type = event.get("type")
        payload = event.get("data", {}) or {}
        
        # Resource status now comes from monitor data, so we skip individual resource_status events
        if event_type == "resource_status":
            return
            
        if event_type == "project_status_snapshot":
            statuses = payload.get("statuses") or {}
            if statuses:
                self.project_status.update(statuses)
                self._queue_project_updates(list(statuses.keys()))
            main_window = self.window()
            if main_window and hasattr(main_window, "tabs"):
                main_window.tabs.setEnabled(True)
                if hasattr(main_window, "statusBar"):
                    main_window.statusBar().showMessage("Ready", 3000)
            return
            
        project = payload.get("project")
        action = payload.get("action")
        if not project:
            return

        def _request_scan(resources: list):
            regions = extract_regions_from_resources(resources)
            if regions and self.monitor_tab:
                self.monitor_tab.monitor_service.request_scan(regions=regions)

        status_map = {
            "deploy_requested": "deploying",
            "deploy_confirmed": "deploying",
            "deploy_confirm_error": "failed",
            "terminate_requested": "terminating",
            "terminate_progress": "terminating",
            "terminate_complete": "terminating",
            "terminate_confirm_error": "running",
        }

        status = None
        if event_type == "deploy" and event.get("status") in ("in_progress", "success"):
            status = "deploying"
        elif event_type in status_map:
            status = status_map[event_type]
        elif event_type == "terminate_confirmed":
            status = "draft"
            confirmed_resources = payload.get("confirmed_resources", [])
            if confirmed_resources:
                _request_scan(confirmed_resources)
        elif event_type == "power_confirmed":
            if action == "start":
                status = "running"
            elif action == "stop":
                status = "stopped"
            resources = payload.get("resources", [])
            if resources:
                _request_scan(resources)
        elif event_type == "power_confirm_error":
            resources = payload.get("resources", [])
            if resources:
                _request_scan(resources)

        if status:
            self.project_status[project] = status
            self._queue_project_update(project)

    def _queue_project_update(self, project_name: str):
        if not project_name:
            return
        self._pending_project_updates.add(project_name)
        if not self._row_update_timer.isActive():
            self._row_update_timer.start(250)

    def _queue_project_updates(self, project_names: list[str]):
        for name in project_names:
            if name:
                self._pending_project_updates.add(name)
        if self._pending_project_updates and not self._row_update_timer.isActive():
            self._row_update_timer.start(250)

    def _queue_all_projects(self):
        projects = list_projects()
        self._queue_project_updates([p["name"] for p in projects])

    def _apply_project_updates(self):
        if not self._pending_project_updates:
            return
        if self._refreshing:
            self._row_update_timer.start(250)
            return

        pending = self._pending_project_updates
        self._pending_project_updates = set()

        projects = list_projects()
        project_by_name = {p["name"]: p for p in projects}

        needs_full_refresh = False
        for project_name in pending:
            if project_name not in project_by_name:
                needs_full_refresh = True
                break
            if project_name not in self._rows_by_project:
                needs_full_refresh = True
                break

        if needs_full_refresh:
            self.refresh_projects()
            return

        self.list_widget.setUpdatesEnabled(False)
        try:
            for project_name in pending:
                project = project_by_name.get(project_name)
                if not project:
                    continue
                monitor_resources = []
                if self.monitor_tab:
                    monitor_resources = self.monitor_tab.get_resources_by_project(project["name"])
                resource_count = len(monitor_resources) if monitor_resources else 0
                status = self.project_status.get(project_name) or project.get("status") or "draft"
                blueprint = load_project(project["slug"])
                row = self._rows_by_project.get(project_name)
                if row:
                    row.update_data(
                        project,
                        resource_count,
                        status,
                        blueprint=blueprint,
                        monitor_resources=monitor_resources,
                    )
        finally:
            self.list_widget.setUpdatesEnabled(True)
    
    def refresh_projects(self):
        """Queue a refresh with debouncing to prevent rapid successive calls."""
        if self._refreshing:
            # Already refreshing, just queue another refresh
            self._pending_refresh = True
            return
        
        self._pending_refresh = True
        # Debounce: wait 150ms before actually refreshing
        # This prevents double-free errors when doing too much too fast
        self._refresh_timer.start(150)
    
    def _do_refresh_projects(self):
        """Actually perform the refresh (called after debounce timer)."""
        if self._refreshing:
            # If we're still refreshing, queue another one
            self._pending_refresh = True
            self._refresh_timer.start(150)
            return
        
        if not self._pending_refresh:
            return
        
        self._refreshing = True
        self._pending_refresh = False
        
        self.list_widget.setUpdatesEnabled(False)
        try:
            logger.debug("Refreshing project list")
            
            # Clear all references BEFORE clearing the widget to break circular refs
            self._rows_by_project = {}
            
            # Manually remove items from the end to avoid iterator issues
            # This is safer than clear() which can cause double deletion
            while self.list_widget.count() > 0:
                item = self.list_widget.takeItem(0)
                if item:
                    widget = self.list_widget.itemWidget(item)
                    if widget:
                        # Remove widget from item before deleting item
                        self.list_widget.removeItemWidget(item)
                    del item  # Explicit deletion
            
        finally:
            self._refreshing = False
            self.list_widget.setUpdatesEnabled(True)
        
        # Continue with building new list...
        projects = list_projects()
        
        if not projects:
            item = QListWidgetItem("No projects yet. Click '+ New Project' to create one.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(Qt.GlobalColor.gray)
            self.list_widget.addItem(item)
            return
        
        for project in projects:
            monitor_resources = []
            if self.monitor_tab:
                monitor_resources = self.monitor_tab.get_resources_by_project(project['name'])

            project_name = project["name"]
            resource_count = len(monitor_resources) if monitor_resources else 0
            status = self.project_status.get(project_name)
            if not status:
                status = project.get("status") or "draft"
            
            item = QListWidgetItem(self.list_widget)
            # Increased height to prevent text cutoff
            item.setSizeHint(QSize(0, 110))
            
            blueprint = load_project(project["slug"])
            row = ProjectRowWidget(
                project,
                resource_count,
                status,
                blueprint=blueprint,
                list_item=item,
                monitor_resources=monitor_resources,
                expanded=project["slug"] in self._expanded_projects,
            )
            self._rows_by_project[project_name] = row
            
            row.action_edit.connect(self.project_edit.emit)
            row.action_monitor.connect(self.project_monitor.emit)
            row.view_toggled.connect(self._on_view_toggled)
            row.action_terminate.connect(self._terminate_project)
            row.action_delete_file.connect(self._delete_file)
            row.action_deploy.connect(self._deploy_project)
            # Store action in lambda closure but use weak references pattern
            def make_power_handler(action):
                return lambda name: self._power_project(name, action)
            row.action_start.connect(make_power_handler("start"))
            row.action_stop.connect(make_power_handler("stop"))
            
            self.list_widget.setItemWidget(item, row)

    def _on_view_toggled(self, slug: str, expanded: bool):
        if expanded:
            self._expanded_projects.add(slug)
        else:
            self._expanded_projects.discard(slug)
        self._save_ui_state()

    def _load_ui_state(self):
        try:
            if not self._ui_state_path.exists():
                return
            raw = json.loads(self._ui_state_path.read_text(encoding="utf-8"))
            expanded = raw.get("expanded_projects") or []
            if isinstance(expanded, list):
                self._expanded_projects = {s for s in expanded if isinstance(s, str)}
        except Exception:
            return

    def _save_ui_state(self):
        try:
            self._ui_state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"expanded_projects": sorted(self._expanded_projects)}
            self._ui_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            return
            
    def _delete_file(self, slug):
        if delete_project(slug):
            self.refresh_projects()
        else:
            QMessageBox.warning(self, "Error", "Could not delete project file.")

    def _deploy_project(self, slug):
        blueprint = load_project(slug)
        if not blueprint: return
        project_name = blueprint.get('project', {}).get('name', 'Project')
        current_status = self.project_status.get(project_name)
        if current_status == "deploying":
            QMessageBox.warning(self, "Already Deploying", f"'{project_name}' is currently being deployed.")
            return
        if current_status == "terminating":
            QMessageBox.warning(self, "Terminating", f"'{project_name}' is currently terminating.")
            return
        # Optimistic UI update
        self.project_status[project_name] = "deploying"
        self._queue_project_update(project_name)

        worker = ProjectDeployWorker(blueprint, parent=self)
        
        def on_finished(success, msg):
            main_window = self.window()
            if main_window and hasattr(main_window, 'statusBar'):
                status_msg = f"✓ Deployment complete: {project_name}" if success else f"✗ Deployment failed: {msg}"
                main_window.statusBar().showMessage(status_msg, 10000)
            if success:
                # stay in deploying until scan confirms, main window will flip to running
                self.project_status[project_name] = "deploying"
            else:
                self.project_status[project_name] = "failed"
            self._queue_project_update(project_name)
            
        worker.finished.connect(on_finished)
        worker.start()

    def _power_project(self, project_name, action):
        monitor_tab = self.monitor_tab
        # Use shared PowerWorker
        worker = PowerWorker(project_name, action, self, monitor_resources=monitor_tab.resources if monitor_tab else None)
        previous_status = self.project_status.get(project_name)
        self.project_status[project_name] = "starting" if action == "start" else "stopping"
        self._queue_project_update(project_name)
        
        def on_finished(success, msg):
            if success:
                main_window = self.window()
                if main_window and hasattr(main_window, 'statusBar'):
                    main_window.statusBar().showMessage(f"✓ {action.capitalize()}: {project_name} - {msg}", 10000)
                self.project_status[project_name] = "running" if action == "start" else "stopped"
                self._queue_project_update(project_name)
            else:
                if previous_status:
                    self.project_status[project_name] = previous_status
                    self._queue_project_update(project_name)
                QMessageBox.warning(self, "Error", msg)
                
        worker.finished.connect(on_finished)
        worker.start()

    def _terminate_project(self, project_name):
        current_status = self.project_status.get(project_name)
        if current_status == "terminating":
            return
        # Optimistic UI update
        self.project_status[project_name] = "terminating"
        self._queue_project_update(project_name)
            
        monitor_tab = self.monitor_tab
        if not monitor_tab:
            QMessageBox.warning(self, "Error", "Monitor tab not available.")
            return

        # Filter resources for this project
        resources_to_delete = monitor_tab.get_resources_by_project(project_name)
        
        if not resources_to_delete:
            QMessageBox.information(self, "No Resources", f"No running resources found for project '{project_name}'.")
            return
            
        # Confirmation
        reply = QMessageBox.question(
            self,
            "Confirm Termination",
            f"Are you sure you want to terminate {len(resources_to_delete)} resources for '{project_name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Use DeleteWorker (Shared Logic)
        # Store worker in self to prevent GC
        self._current_worker = DeleteWorker(
            resources_to_delete, parent=self, project_name=project_name
        )
        
        def on_finished(success_ids, errors):
            main_window = self.window()
            if main_window and hasattr(main_window, 'statusBar'):
                if not errors:
                    msg = f"✓ Termination complete: {project_name} ({len(success_ids)} resources)"
                else:
                    msg = f"⚠ Termination completed with {len(errors)} errors"
                main_window.statusBar().showMessage(msg, 10000)
            
            if errors:
                error_msg = "\\n".join(errors[:5])
                if len(errors) > 5:
                    error_msg += f"\\n...and {len(errors)-5} more."
                QMessageBox.warning(self, "Termination Errors", f"Some resources failed to delete:\\n{error_msg}")
                
            self._current_worker = None # Cleanup
            
        self._current_worker.finished.connect(on_finished)
        self._current_worker.start()


class MainWindow(QMainWindow):
    managed_vpc_ready = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pockitect - AWS Infrastructure Wizard")
        self.setMinimumSize(1000, 700)
        
        init_storage()
        # Initialize region cache if it doesn't exist or is empty
        from storage import load_project_regions_cache
        cached_regions = load_project_regions_cache()
        if not cached_regions:
            # Refresh cache from actual projects
            write_project_regions_cache()
        
        self.command_listener = CommandListener()
        self.command_listener.start()

        self.confirmation_listener = ConfirmationListener()
        self.confirmation_listener.start()

        self.monitor_service = ResourceMonitoringService(self)
        self.monitor_service.start()
        
        self.projects_dir = get_workspace_root() / DEFAULT_PROJECTS_DIR
        self.watcher = ProjectWatcher(self.projects_dir, parent=self)
        
        self._setup_ui()
        
        # Load and apply theme from preferences
        theme_name = get_preference("theme", "modern_dark")
        self.apply_theme(theme_name)
        
        self.status_event_service = StatusEventService(self)
        self.status_event_service.status_event.connect(self.project_list.handle_status_event)
        self.status_event_service.status_event.connect(self._on_status_event)
        self.status_event_service.scan_event.connect(self.monitor_service.handle_status_event)
        self.status_event_service.start()
        self._connect_signals()
        self.managed_vpc_ready.connect(self._ensure_managed_vpcs_ui)
        self.watcher.start()
        
        # Set up periodic scan timer (every 15 seconds)
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._trigger_periodic_scan)
        self._scan_timer.start(15000)  # 15 seconds in milliseconds
        
        # Trigger initial scan on application load
        self._trigger_periodic_scan()
        
        self._unlock_loading_state("Ready")
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        projects_container = QWidget()
        projects_layout = QVBoxLayout(projects_container)
        projects_layout.setContentsMargins(20, 20, 20, 20)
        
        self.monitor_tab = ResourceMonitorWidget(self.monitor_service)
        
        self.project_list = ProjectListWidget(parent=self, monitor_tab=self.monitor_tab)
        projects_layout.addWidget(self.project_list)
        
        self.monitor_tab.scan_completed.connect(self._on_scan_resources_update)
        self.monitor_tab.scan_completed.connect(lambda _: self.project_list._queue_all_projects())
        
        self.tabs.addTab(projects_container, "📁 Projects")
        self.tabs.addTab(self.monitor_tab, "🌐 Monitor")
        self.tabs.addTab(QuotasTab(), "📊 Quotas")
        self.tabs.addTab(AIAgentTab(monitor_tab=self.monitor_tab), "🤖 AI Agent")
        from settings_tab import SettingsTab
        self.tabs.addTab(SettingsTab(self._ensure_managed_vpcs, parent=self), "Settings")
        
        layout.addWidget(self.tabs)
        self.tabs.setEnabled(False)
        self.statusBar().showMessage("Loading AWS state...", 0)
        self._latest_resources = []
        self._snapshot_sent = False
        self._completed_regions = set()
        self._pending_deploy_scan: Dict[str, str] = {}
        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.setSingleShot(True)
        self._snapshot_timer.timeout.connect(self._emit_snapshot_if_ready)
    
    def _connect_signals(self):
        self.project_list.new_btn.clicked.connect(self._on_new_project)
        self.project_list.project_edit.connect(self._on_open_project)
        self.project_list.project_monitor.connect(self._on_monitor_project)
        self.watcher.projects_changed.connect(self._on_projects_changed)
        self.monitor_service.scan_error.connect(self._unlock_loading_state)
    
    def _trigger_periodic_scan(self):
        """Trigger a resource scan - called on timer and on application load."""
        self.monitor_service.request_scan(regions=None)

    def _ensure_managed_vpcs(self):
        def worker():
            logger = logging.getLogger(__name__)
            logger.info("Managed VPC check starting.")
            service = ManagedVpcService()
            mapping = service.load_mapping()
            regions_with_existing = {}

            for region in ALL_REGIONS:
                vpcs = service.list_vpcs(region)
                if not vpcs:
                    logger.info("Managed VPC scan: no VPCs found in %s (or scan failed).", region)
                if vpcs:
                    regions_with_existing[region] = [
                        {"id": v.vpc_id, "name": v.name, "cidr": v.cidr_block} for v in vpcs
                    ]

                managed = service.find_managed_vpcs(region)
                if managed:
                    mapping.setdefault(region, {}).update(managed)

            regions_need_prompt = {
                region: vpcs
                for region, vpcs in regions_with_existing.items()
                if any(env not in (mapping.get(region) or {}) for env in MANAGED_ENVS)
            }

            self._managed_vpc_state = {
                "mapping": mapping,
                "regions_need_prompt": regions_need_prompt,
            }
            logger.info("Managed VPC check queued (dispatching UI).")
            self.managed_vpc_ready.emit()
            logger.info("Managed VPC check queued.")

        threading.Thread(target=worker, daemon=True).start()

    def _ensure_managed_vpcs_ui(self):
        logger = logging.getLogger(__name__)
        logger.info("Managed VPC UI flow starting.")
        state = getattr(self, "_managed_vpc_state", {}) or {}
        mapping = state.get("mapping") or {}
        regions_need_prompt = state.get("regions_need_prompt") or {}

        if regions_need_prompt:
            from managed_vpc_dialog import ManagedVpcDialog

            dialog = ManagedVpcDialog(regions_need_prompt, parent=self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                logger.warning("Managed VPC association canceled by user.")
                return
            assignments = dialog.get_assignments()
            for region, envs in assignments.items():
                mapping.setdefault(region, {})
                for env, vpc_choice in envs.items():
                    if vpc_choice != "__create__":
                        mapping[region][env] = vpc_choice

        self.statusBar().showMessage("Ensuring managed VPCs (prod/dev/test)...", 0)

        def create_missing():
            service_local = ManagedVpcService()
            mapping_local = mapping
            missing_total = 0
            created_total = 0
            errors = []
            for region in ALL_REGIONS:
                mapping_local.setdefault(region, {})
                for env in MANAGED_ENVS:
                    if env not in mapping_local[region]:
                        cidr = service_local.default_cidr_for_env(env)
                        vpc_id = service_local.ensure_vpc(region, env, cidr)
                        if vpc_id:
                            mapping_local[region][env] = vpc_id
                            created_total += 1
                            logger.info("Managed VPC created: %s %s -> %s", region, env, vpc_id)
                        else:
                            errors.append(f"{region}:{env}")
                            logger.error("Managed VPC create failed: %s %s", region, env)
                        missing_total += 1

            service_local.save_mapping(mapping_local)
            QTimer.singleShot(
                0,
                lambda: self.statusBar().showMessage(
                    (
                        f"Managed VPCs verified. Created {created_total} missing VPC(s)."
                        if not errors
                        else f"Managed VPCs: {created_total} created, {len(errors)} failed."
                    ),
                    12000,
                ),
            )
            if errors:
                QTimer.singleShot(
                    0,
                    lambda: QMessageBox.warning(
                        self,
                        "Managed VPC Creation Issues",
                        "Some managed VPCs could not be created. "
                        "Check AWS permissions or limits, then restart.\n\n"
                        f"Failed: {', '.join(errors)}",
                    ),
                )

        threading.Thread(target=create_missing, daemon=True).start()
    
    def _on_new_project(self):
        dialog = TemplateSelectorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        template_blueprint = dialog.get_selected_blueprint()
        wizard = InfrastructureWizard(self, template_blueprint=template_blueprint)
        wizard.blueprint_created.connect(self._on_blueprint_created)
        wizard.exec()
    
    def _on_open_project(self, slug):
        blueprint = load_project(slug)
        if not blueprint: return
        wizard = InfrastructureWizard(self)
        wizard.load_draft(blueprint)
        wizard.blueprint_created.connect(self._on_blueprint_created)
        wizard.exec()
        
    def _on_monitor_project(self, project_name):
        self.tabs.setCurrentWidget(self.monitor_tab)
    
    def _on_blueprint_created(self, blueprint: dict):
        save_project(blueprint)
        self.project_list.refresh_projects()
    
    def _on_projects_changed(self):
        self.project_list.refresh_projects()
        write_project_regions_cache()
        self.statusBar().showMessage("Projects updated", 3000)

    def _on_scan_resources_update(self, resources):
        self._latest_resources = resources
        self._resolve_pending_deploys(resources)
        self._emit_snapshot_if_ready()

    def _on_status_event(self, event: dict):
        event_type = event.get("type")
        if event_type == "deploy_confirmed":
            payload = event.get("data", {}) or {}
            project = payload.get("project")
            region = payload.get("region")
            if project and region:
                self._pending_deploy_scan[project] = region
                self.project_list.project_status[project] = "deploying"
                self.project_list._queue_project_update(project)
                self.monitor_service.request_scan(regions=[region])
            return
        if event_type != "scan_chunk":
            return
        status = event.get("status")
        payload = event.get("data", {}) or {}
        region = payload.get("region")
        if status == "error":
            self._unlock_loading_state("Scan error while loading state.")
            return
        if region and region != "global":
            self._completed_regions.add(region)
        if not self._snapshot_sent:
            self._snapshot_timer.start(5000)
        self._emit_snapshot_if_ready()

    def _emit_snapshot_if_ready(self):
        if self._snapshot_sent:
            return
        if len(self._completed_regions) >= 5 or (self._snapshot_timer.isActive() is False):
            self._publish_project_status_snapshot(self._latest_resources)
            self._snapshot_sent = True

    def _resolve_pending_deploys(self, resources):
        if not self._pending_deploy_scan:
            return
        resolved = []
        for project, region in self._pending_deploy_scan.items():
            found = False
            for res in resources:
                if res.region != region:
                    continue
                if res.tags.get("pockitect:project") == project:
                    found = True
                    break
                if res.name and res.name.startswith(project):
                    found = True
                    break
            if found:
                resolved.append(project)

        for project in resolved:
            self._pending_deploy_scan.pop(project, None)
            self.project_list.project_status[project] = "running"
        if resolved:
            self.project_list._queue_project_updates(resolved)

    def _unlock_loading_state(self, message: str):
        self.tabs.setEnabled(True)
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(message, 5000)

    def _publish_project_status_snapshot(self, resources):
        from app.core.redis_client import RedisClient
        from storage import list_projects

        projects = list_projects()
        project_names = [p["name"] for p in projects]
        statuses = ProjectStatusCalculator.calculate_statuses_from_resources(
            resources, project_names
        )

        RedisClient().publish_status(
            "project_status_snapshot",
            data={"statuses": statuses},
            status="success",
        )
    
    def apply_theme(self, theme_name: str):
        """
        Apply a theme to the application.
        
        Args:
            theme_name: Name of the theme to apply
        """
        theme = ThemeManager.get_theme(theme_name)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.qss_string)
    
    def closeEvent(self, event):
        logger.info("Application shutting down...")
        self._scan_timer.stop()
        self.monitor_service.stop()
        self.watcher.stop()
        self.command_listener.stop()
        self.confirmation_listener.stop()
        self.status_event_service.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Pockitect")
    
    # Load theme from preferences or use default
    theme_name = get_preference("theme", "modern_dark")
    theme = ThemeManager.get_theme(theme_name)
    app.setStyleSheet(theme.qss_string)
    
    font = QFont("Ubuntu", 10)
    if not font.exactMatch():
        font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    login_dialog = AWSLoginDialog()
    if not login_dialog.try_auto_login():
        if login_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
