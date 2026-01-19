from ai.agent_service import AgentService


class _FakeContextProvider:
    def get_comprehensive_context(self):
        return {"resources_summary": "", "projects_summary": "", "aws_specs": {}}

    def get_projects_summary(self):
        return "Existing projects:\n- demo (us-east-1) status=draft"


class _FakeYAMLGenerator:
    def __init__(self):
        self.calls = []

    def generate_blueprint(self, user_input, context):
        self.calls.append({"user_input": user_input, "context": context})
        return {"project": {"name": "demo", "region": "us-east-1"}}


class _FakeProjectMatcher:
    def find_project(self, name):
        return {"name": "demo", "slug": "demo"}

    def load_project_by_name(self, name):
        return {"project": {"name": "demo", "region": "us-east-1"}}


class _FakeOllamaClient:
    def health_check(self):
        return True


def _build_service():
    service = AgentService()
    service.ollama_client = _FakeOllamaClient()
    service.context_provider = _FakeContextProvider()
    service.yaml_generator = _FakeYAMLGenerator()
    service.project_matcher = _FakeProjectMatcher()
    return service


def test_detect_intent_create():
    service = AgentService()
    intent = service._detect_intent("Create a new project")

    assert intent.type == "create"
    assert intent.confidence >= 0.5


def test_process_request_create_returns_blueprint():
    service = _build_service()
    response = service.process_request("create a web server")

    assert response.intent.type == "create"
    assert response.blueprint is not None
    assert "Generated YAML" in response.message


def test_process_request_deploy_requires_confirmation():
    service = _build_service()
    response = service.process_request("deploy demo")

    assert response.intent.type == "deploy"
    assert response.requires_confirmation is True
    assert response.confirmation_details["project_name"] == "demo"


def test_process_request_power_requires_confirmation():
    service = _build_service()
    response = service.process_request("stop demo")

    assert response.intent.type == "power"
    assert response.requires_confirmation is True
    assert response.confirmation_details["action"] == "stop"


def test_process_request_terminate_requires_confirmation():
    service = _build_service()
    response = service.process_request("terminate demo")

    assert response.intent.type == "terminate"
    assert response.requires_confirmation is True


def test_process_request_query_returns_summary():
    service = _build_service()
    response = service.process_request("list projects")

    assert response.intent.type == "query"
    assert "Existing projects" in response.message
