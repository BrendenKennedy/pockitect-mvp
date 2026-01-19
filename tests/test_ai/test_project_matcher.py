from ai.project_matcher import ProjectMatcher


def test_find_project_exact_match(monkeypatch):
    projects = [{"name": "Demo Project", "slug": "demo-project"}]
    monkeypatch.setattr("ai.project_matcher.list_projects", lambda: projects)

    matcher = ProjectMatcher()
    found = matcher.find_project("Demo Project")

    assert found == projects[0]


def test_find_project_fuzzy_match(monkeypatch):
    projects = [{"name": "demo project", "slug": "demo-project"}]
    monkeypatch.setattr("ai.project_matcher.list_projects", lambda: projects)

    matcher = ProjectMatcher()
    found = matcher.find_project("demo")

    assert found == projects[0]


def test_load_project_by_name(monkeypatch):
    projects = [{"name": "Demo Project", "slug": "demo-project"}]
    monkeypatch.setattr("ai.project_matcher.list_projects", lambda: projects)
    monkeypatch.setattr("ai.project_matcher.load_project", lambda slug: {"project": {"name": "Demo Project"}})

    matcher = ProjectMatcher()
    blueprint = matcher.load_project_by_name("Demo Project")

    assert blueprint["project"]["name"] == "Demo Project"
