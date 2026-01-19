import json
import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from app.core.redis_client import RedisClient
from app.core.aws.scanner import ScannedResource

@pytest.fixture
def mock_project_list(qtbot, monkeypatch):
    """Setup MainWindow with a mocked project list for lifecycle tests."""
    from main import MainWindow
    from monitor_service import ResourceMonitoringService
    from app.core.listeners import CommandListener
    from watcher import ProjectWatcher

    monkeypatch.setattr(ResourceMonitoringService, "start", lambda self: None)
    monkeypatch.setattr(CommandListener, "start", lambda self: None)
    monkeypatch.setattr(ProjectWatcher, "start", lambda self: None)

    window = MainWindow()
    qtbot.addWidget(window)
    
    # Mock storage.list_projects to return a test project
    test_project = {"name": "LifecycleProject", "region": "us-east-1"}
    with patch('main.list_projects', return_value=[test_project]):
        window.project_list.refresh_projects()
        
    return window

@pytest.mark.e2e
@pytest.mark.gui
def test_gui_power_cycle(qtbot, mock_project_list, monkeypatch):
    """
    Test Start/Stop functionality.
    """
    window = mock_project_list
    project_list = window.project_list
    
    # Verify project is listed
    assert project_list.list_widget.count() == 1
    item = project_list.list_widget.itemWidget(project_list.list_widget.item(0))
    
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
            "type": "power",
            "status": "success",
            "request_id": request_id,
            "data": {"message": "Power action complete."},
        })

    RedisClient._instance = SimpleNamespace(client=fake_client, publish_command=fake_publish_command)

    from workers import PowerWorker

    def eager_start(self):
        self.run()

    monkeypatch.setattr(PowerWorker, "start", eager_start)

    try:
        with patch('workers.ResourceTracker') as MockTracker:
            mock_tracker = MockTracker.return_value
            mock_res_ec2 = MagicMock()
            mock_res_ec2.resource_id = 'i-123'
            mock_res_ec2.region = 'us-east-1'

            mock_res_rds = MagicMock()
            mock_res_rds.resource_id = 'db-123'
            mock_res_rds.region = 'us-east-1'

            def get_resources(project, resource_type):
                if resource_type == 'ec2_instance': return [mock_res_ec2]
                if resource_type == 'rds_instance': return [mock_res_rds]
                return []

            mock_tracker.get_active_resources.side_effect = get_resources

            if not item:
                item = project_list.list_widget.itemWidget(project_list.list_widget.item(0))

            item.action_start.emit("LifecycleProject")
            item.action_stop.emit("LifecycleProject")
    finally:
        RedisClient._instance = None

@pytest.mark.e2e
@pytest.mark.gui
def test_gui_termination_flow(qtbot, mock_project_list, monkeypatch):
    """
    Test Project Termination using the new DeleteWorker logic.
    """
    window = mock_project_list
    project_list = window.project_list
    item = project_list.list_widget.itemWidget(project_list.list_widget.item(0))

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
        for resource in data.get("resources", []):
            fake_pubsub.push({
                "type": "terminate_progress",
                "status": "in_progress",
                "request_id": request_id,
                "data": {
                    "resource_id": resource["id"],
                    "resource_type": resource["type"],
                    "region": resource["region"],
                },
            })
        fake_pubsub.push({
            "type": "terminate_complete",
            "status": "success",
            "request_id": request_id,
            "data": {"total": len(data.get("resources", []))},
        })

    RedisClient._instance = SimpleNamespace(client=fake_client, publish_command=fake_publish_command)

    from workers import DeleteWorker

    def eager_start(self):
        self.run()

    monkeypatch.setattr(DeleteWorker, "start", eager_start)

    try:
        res = MagicMock(spec=ScannedResource)
        res.id = "i-terminate"
        res.type = "ec2_instance"
        res.region = "us-east-1"
        res.tags = {'pockitect:project': 'LifecycleProject'}
        res.details = {}

        window.monitor_tab.resources = [res]

        item.action_terminate.emit("LifecycleProject")
    finally:
        RedisClient._instance = None
