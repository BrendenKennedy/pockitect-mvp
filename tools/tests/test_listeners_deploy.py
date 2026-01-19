from app.core.listeners import CommandListener


class _FakeRedis:
    def __init__(self):
        self.status_events = []

    def publish_status(self, event_type, data=None, project_id=None, request_id=None, **extra_fields):
        payload = {"type": event_type, "data": data or {}, "request_id": request_id}
        payload.update(extra_fields)
        self.status_events.append(payload)


class _FailingDeployer:
    async def deploy(self, template_path, progress_callback=None):
        raise RuntimeError("Deploy failed")


def test_deploy_handler_failure(monkeypatch):
    listener = CommandListener()
    listener.redis = _FakeRedis()

    monkeypatch.setattr("app.core.listeners.ResourceDeployer", lambda: _FailingDeployer())

    listener._handle_deploy({"template_path": "/tmp/template.yaml"}, request_id="req-1")

    assert any(
        event.get("status") == "error" and "Deploy failed" in event["data"].get("error", "")
        for event in listener.redis.status_events
    )
