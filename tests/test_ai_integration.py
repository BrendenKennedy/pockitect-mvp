from ai.agent_service import AgentService
from ai.validator import BlueprintValidator
from ai.command_executor import CommandExecutor


class _FakeContextProvider:
    def get_comprehensive_context(self):
        return {"resources_summary": "", "projects_summary": "", "aws_specs": {}}


class _FakeYAMLGenerator:
    def generate_blueprint(self, user_input, context):
        return {
            "project": {"name": "demo", "region": "us-east-1"},
            "network": {},
            "compute": {},
            "data": {},
            "security": {},
        }


def test_end_to_end_create_flow():
    service = AgentService()
    service.ollama_client = type("_FakeOllama", (), {"health_check": lambda self: True})()
    service.context_provider = _FakeContextProvider()
    service.yaml_generator = _FakeYAMLGenerator()

    response = service.process_request("create a demo project")

    assert response.blueprint is not None
    validator = BlueprintValidator()
    valid, errors = validator.validate(response.blueprint)
    assert valid is True
    assert errors == []


def test_command_executor_scan_publishes(monkeypatch):
    published = {}

    class _FakeRedis:
        def publish_command(self, event_type, data=None, request_id=None):
            published["event_type"] = event_type
            published["data"] = data or {}
            published["request_id"] = request_id

    monkeypatch.setattr("ai.command_executor.RedisClient", lambda: _FakeRedis())

    executor = CommandExecutor()
    executor.scan_regions(regions=["us-east-1"])

    assert published["event_type"] == "scan_all_regions"
    assert published["data"]["regions"] == ["us-east-1"]
