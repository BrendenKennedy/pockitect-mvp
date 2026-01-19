import yaml

from ai.yaml_generator import YAMLGenerator


class _FakeOllama:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return self.response


def test_build_prompt_includes_context():
    generator = YAMLGenerator(_FakeOllama(""))
    context = {
        "resources_summary": "resources",
        "projects_summary": "projects",
        "aws_specs": {"regions": ["us-east-1"]},
    }

    prompt = generator._build_prompt("hello", context)

    assert "resources" in prompt
    assert "projects" in prompt
    assert "us-east-1" in prompt
    assert "User Request: \"hello\"" in prompt


def test_parse_yaml_from_fenced_block():
    generator = YAMLGenerator(_FakeOllama(""))
    content = "```yaml\nproject:\n  name: demo\n```\n"

    parsed = generator._parse_yaml_from_response(content)

    assert parsed == {"project": {"name": "demo"}}


def test_parse_yaml_from_plain_text():
    generator = YAMLGenerator(_FakeOllama(""))
    content = "project:\n  name: demo\n"

    parsed = generator._parse_yaml_from_response(content)

    assert parsed == {"project": {"name": "demo"}}


def test_generate_blueprint_applies_defaults():
    response_yaml = yaml.safe_dump(
        {"project": {"name": "demo", "region": "us-west-2"}, "compute": {"instance_type": "t3.micro"}},
        sort_keys=False,
    )
    generator = YAMLGenerator(_FakeOllama(response_yaml))

    blueprint = generator.generate_blueprint("make demo", {"resources_summary": "", "projects_summary": "", "aws_specs": {}})

    assert blueprint["project"]["name"] == "demo"
    assert blueprint["project"]["region"] == "us-west-2"
    assert "network" in blueprint
    assert "security" in blueprint
