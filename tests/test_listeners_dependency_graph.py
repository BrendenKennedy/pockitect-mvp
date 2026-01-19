from app.core.listeners import CommandListener, GraphNode


class _FakeRedis:
    def publish_status(self, *args, **kwargs):
        pass


def test_dependency_graph_topology(monkeypatch):
    listener = CommandListener()
    listener.redis = _FakeRedis()

    def _fake_children(node):
        if node.resource_type == "vpc":
            return [GraphNode("subnet-1", "subnet", node.region)]
        return []

    monkeypatch.setattr(listener, "_discover_children", _fake_children)

    resources = [{"id": "vpc-1", "type": "vpc", "region": "us-east-1"}]
    graph = listener._build_dependency_graph(resources)
    order = listener._topological_sort(graph)

    assert order[0].resource_type == "vpc"
    assert any(node.resource_type == "subnet" for node in order)
