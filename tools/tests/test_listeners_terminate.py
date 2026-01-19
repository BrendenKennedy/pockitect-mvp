from app.core.listeners import CommandListener, GraphNode


class _FakeRedis:
    def __init__(self):
        self.status_events = []

    def publish_status(self, event_type, data=None, project_id=None, request_id=None, **extra_fields):
        payload = {"type": event_type, "data": data or {}, "request_id": request_id}
        payload.update(extra_fields)
        self.status_events.append(payload)


class _FakeDeleter:
    def __init__(self):
        self.calls = []

    def delete_resource(self, resource_id, resource_type, region):
        self.calls.append((resource_id, resource_type, region))
        return True


def test_terminate_handler_order(monkeypatch):
    listener = CommandListener()
    listener.redis = _FakeRedis()

    fake_deleter = _FakeDeleter()
    monkeypatch.setattr("app.core.listeners.ResourceDeleter", lambda: fake_deleter)

    node_a = GraphNode("vpc-1", "vpc", "us-east-1")
    node_b = GraphNode("subnet-1", "subnet", "us-east-1")

    monkeypatch.setattr(listener, "_build_dependency_graph", lambda resources: {node_a: {node_b}, node_b: set()})
    monkeypatch.setattr(listener, "_topological_sort", lambda graph: [node_a, node_b])

    listener._handle_terminate(
        {"resources": [{"id": "vpc-1", "type": "vpc", "region": "us-east-1"}]},
        request_id="req-1",
    )

    assert fake_deleter.calls[0] == ("subnet-1", "subnet", "us-east-1")
    assert fake_deleter.calls[1] == ("vpc-1", "vpc", "us-east-1")
    assert any(event["type"] == "terminate_complete" for event in listener.redis.status_events)
