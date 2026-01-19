from ai.validator import BlueprintValidator
from storage import create_empty_blueprint


def test_validate_accepts_valid_blueprint():
    validator = BlueprintValidator()
    blueprint = create_empty_blueprint("demo")

    valid, errors = validator.validate(blueprint)

    assert valid is True
    assert errors == []


def test_validate_rejects_invalid_region_and_instance():
    validator = BlueprintValidator()
    blueprint = create_empty_blueprint("demo")
    blueprint["project"]["region"] = "invalid-region"
    blueprint["compute"]["instance_type"] = "invalid-instance"

    valid, errors = validator.validate(blueprint)

    assert valid is False
    assert any("Unsupported region" in err for err in errors)
    assert any("Unsupported instance type" in err for err in errors)


def test_fix_common_issues_restores_defaults():
    validator = BlueprintValidator()
    blueprint = {"project": {"name": "demo"}}

    fixed = validator.fix_common_issues(blueprint)

    assert fixed["project"]["region"] == "us-east-1"
    assert "network" in fixed
    assert "compute" in fixed
