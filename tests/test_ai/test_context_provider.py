from ai.context_provider import ContextProvider


class _Resource:
    def __init__(self, region, rtype, tags):
        self.region = region
        self.type = rtype
        self.tags = tags


class _MonitorTab:
    def __init__(self, resources):
        self.resources = resources


def test_get_projects_summary(monkeypatch):
    projects = [
        {"name": "demo", "region": "us-east-1", "status": "draft"},
        {"name": "prod", "region": "us-west-2", "status": "running"},
    ]
    monkeypatch.setattr("ai.context_provider.list_projects", lambda: projects)

    provider = ContextProvider()
    summary = provider.get_projects_summary()

    assert "demo" in summary
    assert "us-east-1" in summary
    assert "prod" in summary


def test_get_resources_summary():
    resources = [
        _Resource("us-east-1", "ec2_instance", {"pockitect:project": "demo"}),
        _Resource("us-east-1", "rds_instance", {"pockitect:project": "demo"}),
        _Resource("us-west-2", "s3_bucket", {}),
    ]
    provider = ContextProvider(monitor_tab=_MonitorTab(resources))

    summary = provider.get_resources_summary()

    assert "us-east-1" in summary
    assert "ec2_instance" in summary
    assert "rds_instance" in summary


def test_reference_notes_loading(tmp_path):
    refs = tmp_path / "ai_refs"
    refs.mkdir()
    (refs / "sample.md").write_text("Sample Reference\n- item", encoding="utf-8")

    provider = ContextProvider(reference_dir=refs)
    notes = provider.get_reference_notes()

    assert "Reference Notes:" in notes
    assert "sample" in notes
    assert "Sample Reference" in notes
