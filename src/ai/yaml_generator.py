"""Generate Pockitect YAML blueprints from natural language."""

from __future__ import annotations

import re
from typing import Any, Dict

import yaml

from storage import create_empty_blueprint
from .ollama_client import OllamaClient
from .prompts import YAML_SYSTEM_PROMPT


class YAMLGenerator:
    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.ollama_client = ollama_client or OllamaClient()

    def generate_blueprint(self, user_input: str, context: Dict[str, Any], history: str = "") -> Dict[str, Any]:
        system_prompt = YAML_SYSTEM_PROMPT
        prompt = self._build_prompt(user_input, context, history=history)
        response = self.ollama_client.generate(prompt, system_prompt=system_prompt)
        blueprint = self._parse_yaml_from_response(response)
        merged = self._apply_defaults(blueprint)
        self._validate_blueprint(merged)
        return merged

    def _build_prompt(self, user_input: str, context: Dict[str, Any], history: str = "") -> str:
        schema_definition = self._schema_definition()
        examples = self._few_shot_examples()
        history_section = f"Conversation History:\n{history}\n\n" if history else ""
        budget_section = ""
        if context.get("budget_summary"):
            budget_section = f"Current Budget Status:\n{context.get('budget_summary')}\n\n"
        reference_section = ""
        if context.get("reference_notes"):
            reference_section = f"Reference Notes:\n{context.get('reference_notes')}\n\n"
        freshness_section = ""
        if context.get("context_freshness"):
            freshness_section = f"Context Freshness:\n{context.get('context_freshness')}\n\n"
        return "".join(
            [
                history_section,
                "Current AWS State:\n",
                f"{context.get('resources_summary')}\n\n",
                budget_section,
                reference_section,
                "Existing Projects:\n",
                f"{context.get('projects_summary')}\n\n",
                freshness_section,
                "Available Options:\n",
                f"{context.get('aws_specs')}\n\n",
                "YAML Schema:\n",
                f"{schema_definition}\n\n",
                f"{examples}\n\n",
                f'User Request: "{user_input}"\n\n',
                "If this is a refinement of a previous request, modify the last blueprint accordingly.\n",
                "Generate ONLY valid YAML matching the schema above. No explanations, just YAML.",
            ]
        )

    def _schema_definition(self) -> str:
        example = create_empty_blueprint("example-project")
        return yaml.safe_dump(example, sort_keys=False)

    def _few_shot_examples(self) -> str:
        return (
            "Example Request: \"Create a small web server in us-east-1\"\n"
            "Example YAML:\n"
            "project:\n"
            "  name: example-web\n"
            "  description: Simple web server\n"
            "  region: us-east-1\n"
            "  created_at: \"2026-01-01T00:00:00Z\"\n"
            "  owner: developer\n"
            "  cost: null\n"
            "network:\n"
            "  vpc_id: null\n"
            "  subnet_id: null\n"
            "  security_group_id: null\n"
            "  vpc_env: dev\n"
            "  subnet_type: public\n"
            "  rules:\n"
            "    - port: 22\n"
            "      protocol: tcp\n"
            "      cidr: 0.0.0.0/0\n"
            "      description: SSH\n"
            "  status: pending\n"
            "compute:\n"
            "  instance_type: t3.micro\n"
            "  image_id: ubuntu-22.04\n"
            "  image_name: Ubuntu 22.04\n"
            "  user_data: \"\"\n"
            "  instance_id: null\n"
            "  status: pending\n"
            "data:\n"
            "  db:\n"
            "    engine: null\n"
            "    instance_class: null\n"
            "    allocated_storage_gb: null\n"
            "    username: null\n"
            "    password: null\n"
            "    endpoint: null\n"
            "    status: skipped\n"
            "  s3_bucket:\n"
            "    name: null\n"
            "    arn: null\n"
            "    status: skipped\n"
            "security:\n"
            "  key_pair:\n"
            "    name: example-web-key\n"
            "    mode: generate\n"
            "    key_pair_id: null\n"
            "    private_key_pem: null\n"
            "    status: pending\n"
            "  certificate:\n"
            "    domain: null\n"
            "    mode: skip\n"
            "    cert_arn: null\n"
            "    status: skipped\n"
            "  iam_role:\n"
            "    role_name: \"\"\n"
            "    policy_document: {}\n"
            "    arn: null\n"
            "    instance_profile_arn: null\n"
            "    status: pending\n"
        )

    def _parse_yaml_from_response(self, response: str) -> Dict[str, Any]:
        content = response.strip()
        fenced = re.findall(r"```(?:yaml)?\n(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            content = fenced[0].strip()
        parsed = self._safe_yaml_load(content)
        if parsed is None:
            candidate = self._extract_yaml_candidate(content)
            parsed = self._safe_yaml_load(candidate) if candidate else None
        if not isinstance(parsed, dict):
            raise ValueError("Generated YAML is not a mapping.")
        return parsed

    def _apply_defaults(self, blueprint: Dict[str, Any]) -> Dict[str, Any]:
        project = blueprint.get("project", {})
        name = project.get("name") or "Untitled Project"
        description = project.get("description") or ""
        region = project.get("region") or "us-east-1"
        owner = project.get("owner") or ""

        base = create_empty_blueprint(name, description, region, owner)

        def merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in src.items():
                if isinstance(value, dict):
                    node = dst.get(key)
                    if isinstance(node, dict):
                        merge(node, value)
                    else:
                        dst[key] = value
                elif key not in dst or dst[key] is None:
                    dst[key] = value
            return dst

        merged = merge(base, blueprint)
        return merged

    def _safe_yaml_load(self, content: str) -> Dict[str, Any] | None:
        try:
            return yaml.safe_load(content)
        except Exception:
            return None

    def _extract_yaml_candidate(self, content: str) -> str | None:
        match = re.search(r"(?ms)^project:\s", content)
        if not match:
            return None
        return content[match.start():].strip()

    def _validate_blueprint(self, blueprint: Dict[str, Any]) -> None:
        from .validator import BlueprintValidator

        validator = BlueprintValidator()
        valid, errors = validator.validate(blueprint)
        if not valid:
            raise ValueError(f"Generated YAML failed validation: {errors[:3]}")
