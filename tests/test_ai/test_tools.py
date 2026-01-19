from datetime import datetime, timedelta, timezone

from ai.context_provider import ContextProvider
from ai.tools import ToolExecutor, parse_tool_request


class _MonitorTab:
    def __init__(self):
        self.monitor_service = None


class _ContextProvider(ContextProvider):
    def __init__(self):
        super().__init__(monitor_tab=_MonitorTab())


def test_parse_tool_request():
    text = """Here is a tool call:
[TOOL_REQUEST]
name: scan_resources
args: {"regions": ["us-east-1"]}
[/TOOL_REQUEST]
"""
    request = parse_tool_request(text)
    assert request is not None
    assert request.name == "scan_resources"
    assert request.args == {"regions": ["us-east-1"]}


def test_parse_tool_request_missing():
    request = parse_tool_request("no tool here")
    assert request is None


def test_context_freshness_report(monkeypatch):
    provider = _ContextProvider()
    monkeypatch.setattr(provider, "get_resources_age_seconds", lambda: 120)
    monkeypatch.setattr(provider, "get_budget_age_seconds", lambda: 7200)

    report = provider.get_context_freshness_report()

    assert "Resources:" in report
    assert "Costs:" in report
    assert "fresh" in report
    assert "stale" in report


def test_resources_age_seconds(monkeypatch):
    provider = _ContextProvider()
    now = datetime.now(timezone.utc)
    timestamp = (now - timedelta(seconds=90)).isoformat().replace("+00:00", "Z")

    def _mock_get_cached(key):
        if key.endswith("last_resource_scan"):
            return timestamp
        return None

    monkeypatch.setattr(provider, "_get_cached", _mock_get_cached)

    age = provider.get_resources_age_seconds()
    assert age is not None
    assert 80 <= age <= 120


def test_tool_executor_list_projects(monkeypatch):
    provider = _ContextProvider()
    monkeypatch.setattr(provider, "get_projects_summary", lambda: "Existing projects:\n- demo")

    executor = ToolExecutor(provider)
    request = parse_tool_request("[TOOL_REQUEST]\nname: list_projects\nargs: {}\n[/TOOL_REQUEST]")
    assert request is not None
    result = executor.execute(request)

    assert "demo" in result
