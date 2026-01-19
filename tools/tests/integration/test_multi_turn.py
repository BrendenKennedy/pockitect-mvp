from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agent_service import AgentService


class FakeSessionManager:
    def __init__(self, history: str):
        self.history = history
        self.appended = []

    def get_history_for_prompt(self, session_id: str) -> str:
        return self.history

    def append_turn(self, session_id: str, user: str, assistant: str, blueprint: dict):
        self.appended.append((session_id, user, assistant))

    def clear_session(self, session_id: str):
        return None


def test_refinement_flow_uses_history(monkeypatch):
    service = AgentService()
    service.session_manager = FakeSessionManager("Turn 1 User: Create a blog")
    service.ollama_client.health_check = lambda: True
    service.context_provider.get_comprehensive_context = lambda: {"aws_specs": {"regions": ["us-east-1"]}}

    captured = {}

    def fake_generate(user_input, context, history=""):
        captured["history"] = history
        return {
            "project": {"name": "refined", "region": "us-east-1"},
            "network": {},
            "compute": {},
            "data": {},
            "security": {},
        }

    service.yaml_generator.generate_blueprint = fake_generate

    response = service.process_request("Make it bigger", session_id="abc123")

    assert response.intent.type == "refine"
    assert "history" in captured and captured["history"]
