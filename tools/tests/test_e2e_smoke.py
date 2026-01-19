import json
import pytest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import Qt

from app.core.redis_client import RedisClient

@pytest.mark.e2e
@pytest.mark.gui
def test_gui_scan_flow_success(qtbot, tmp_path, monkeypatch):
    """
    Full smoke test:
    1. User clicks Scan on Monitor Tab
    2. MonitorService publishes scan command
    3. Listener calls mocked Scanner
    4. Listener updates Redis & publishes status
    5. MonitorService receives update
    6. UI updates tree
    """
    from main import MainWindow
    from monitor_service import ResourceMonitoringService
    from app.core.listeners import CommandListener
    from watcher import ProjectWatcher

    monkeypatch.setattr(ResourceMonitoringService, "start", lambda self: None)
    monkeypatch.setattr(CommandListener, "start", lambda self: None)
    monkeypatch.setattr(ProjectWatcher, "start", lambda self: None)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    
    window.tabs.setCurrentIndex(1)
    monitor_tab = window.monitor_tab
    monitor_tab.monitor_service._scan_cache_dir = tmp_path
    
    assert monitor_tab.tree.topLevelItemCount() == 0
    
    cache_path = tmp_path / "us-east-1.json"
    cache_path.write_text(
        json.dumps([
            {
                "id": "e2e-res-1",
                "type": "ec2_instance",
                "region": "us-east-1",
                "name": "E2E VM",
                "state": "running",
                "details": {},
                "tags": {},
            }
        ]),
        encoding="utf-8",
    )

    with qtbot.waitSignal(monitor_tab.scan_completed, timeout=3000):
        qtbot.mouseClick(monitor_tab.scan_btn, Qt.LeftButton)
        monitor_tab.monitor_service._handle_scan_chunk({
            "type": "scan_chunk",
            "data": {"file": str(cache_path), "region": "us-east-1"},
        })
        monitor_tab.monitor_service._handle_scan_complete({
            "type": "scan_complete",
            "status": "success",
        })

    assert "Scan complete" in monitor_tab.status_label.text()

    assert monitor_tab.tree.topLevelItemCount() == 1
    region_item = monitor_tab.tree.topLevelItem(0)
    assert region_item.text(0) == "us-east-1"

    assert region_item.childCount() == 1
    type_item = region_item.child(0)
    assert type_item.text(0) == "ec2_instance"

    assert type_item.childCount() == 1
    res_item = type_item.child(0)
    assert res_item.text(1) == "e2e-res-1"

@pytest.mark.e2e
@pytest.mark.gui
def test_gui_deployment_failure(qtbot, monkeypatch):
    """
    Test failure path during deployment:
    1. User triggers deployment via Project List
    2. Task Fails
    3. GUI shows error
    """
    from main import MainWindow
    from monitor_service import ResourceMonitoringService
    from app.core.listeners import CommandListener
    from watcher import ProjectWatcher
    from deploy_worker import ProjectDeployWorker

    class FakePubSub:
        def __init__(self):
            self._messages = []
        def subscribe(self, *args, **kwargs):
            return None
        def get_message(self, ignore_subscribe_messages=True, timeout=0.5):
            if self._messages:
                return self._messages.pop(0)
            return None
        def close(self):
            return None
        def push(self, payload):
            self._messages.append({"data": json.dumps(payload)})

    fake_pubsub = FakePubSub()
    fake_client = SimpleNamespace(pubsub=lambda: fake_pubsub)

    def fake_publish_command(event_type, data=None, project_id=None, request_id=None, **extra_fields):
        fake_pubsub.push({
            "type": "deploy",
            "status": "error",
            "request_id": request_id,
            "data": {"error": "Deploy Boom"},
        })

    monkeypatch.setattr(ResourceMonitoringService, "start", lambda self: None)
    monkeypatch.setattr(CommandListener, "start", lambda self: None)
    monkeypatch.setattr(ProjectWatcher, "start", lambda self: None)

    RedisClient._instance = SimpleNamespace(client=fake_client, publish_command=fake_publish_command)

    def eager_start(self):
        self.run()

    monkeypatch.setattr(ProjectDeployWorker, "start", eager_start)

    window = MainWindow()
    qtbot.addWidget(window)

    project_list = window.project_list
    
    blueprint = {
        "project": {"name": "TestProject", "region": "us-east-1"},
        "resources": {}
    }
    
    try:
        with patch('main.load_project', return_value=blueprint):
            project_list._deploy_project("test-slug")
            qtbot.wait(100)

            def check_status():
                if window.statusBar():
                    msg = window.statusBar().currentMessage()
                    return "Deployment failed" in msg and "Deploy Boom" in msg
                return False

            qtbot.waitUntil(check_status, timeout=3000)
    finally:
        RedisClient._instance = None