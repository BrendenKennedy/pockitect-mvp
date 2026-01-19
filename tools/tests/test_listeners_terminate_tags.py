from app.core.listeners import CommandListener


class _FakeRedis:
    def __init__(self):
        self.status_events = []

    def publish_status(self, event_type, data=None, project_id=None, request_id=None, **extra_fields):
        payload = {"type": event_type, "data": data or {}, "request_id": request_id}
        payload.update(extra_fields)
        self.status_events.append(payload)


def test_terminate_skips_foreign_project_tags(monkeypatch):
    listener = CommandListener()
    listener.redis = _FakeRedis()

    monkeypatch.setattr(listener, "_build_dependency_graph", lambda resources: {})

    listener._handle_terminate(
        {
            "resources": [
                {
                    "id": "vpc-1",
                    "type": "vpc",
                    "region": "us-east-1",
                    "tags": {"pockitect:project": "project-a"},
                },
                {
                    "id": "vpc-2",
                    "type": "vpc",
                    "region": "us-east-1",
                    "tags": {"pockitect:project": "project-a,project-b"},
                },
            ]
        },
        request_id="req-1",
    )

    assert any(event["type"] == "terminate_skipped" for event in listener.redis.status_events)
