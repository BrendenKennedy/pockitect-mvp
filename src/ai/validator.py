"""Blueprint validation helpers."""

from __future__ import annotations

from typing import Dict, List, Tuple

from storage import create_empty_blueprint
from wizard.pages.compute import INSTANCE_TYPES, COMMON_AMIS
from wizard.pages.project_basics import AWS_REGIONS
from wizard.pages.data import DB_ENGINES, DB_INSTANCE_CLASSES


class BlueprintValidator:
    def __init__(self) -> None:
        self._valid_regions = {rid for rid, _ in AWS_REGIONS}
        self._valid_instance_types = {iid for iid, _ in INSTANCE_TYPES}
        self._valid_amis = {ami_id for ami_id, _, _ in COMMON_AMIS}
        self._valid_db_engines = {engine for engine, _ in DB_ENGINES}
        self._valid_db_classes = {cls for cls, _ in DB_INSTANCE_CLASSES}

    def validate(self, blueprint: Dict) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        for section in ("project", "network", "compute", "data", "security"):
            if section not in blueprint:
                errors.append(f"Missing required section: {section}")

        project = blueprint.get("project", {})
        if not project.get("name"):
            errors.append("project.name is required")
        region = project.get("region")
        if not region:
            errors.append("project.region is required")
        elif region not in self._valid_regions:
            errors.append(f"Unsupported region: {region}")

        compute = blueprint.get("compute", {})
        instance_type = compute.get("instance_type")
        if instance_type and instance_type not in self._valid_instance_types:
            errors.append(f"Unsupported instance type: {instance_type}")

        image_id = compute.get("image_id")
        if image_id and image_id not in self._valid_amis and not str(image_id).startswith("ami-"):
            errors.append(f"Unsupported image_id: {image_id}")

        data = blueprint.get("data", {})
        db = data.get("db", {})
        if db.get("engine") and db.get("engine") not in self._valid_db_engines:
            errors.append(f"Unsupported db.engine: {db.get('engine')}")
        if db.get("instance_class") and db.get("instance_class") not in self._valid_db_classes:
            errors.append(f"Unsupported db.instance_class: {db.get('instance_class')}")

        return (len(errors) == 0, errors)

    def fix_common_issues(self, blueprint: Dict) -> Dict:
        project = blueprint.get("project") or {}
        name = project.get("name") or "Untitled Project"
        description = project.get("description") or ""
        region = project.get("region") or "us-east-1"
        owner = project.get("owner") or ""

        base = create_empty_blueprint(name, description, region, owner)

        def merge(dst: Dict, src: Dict) -> Dict:
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

        return merge(base, blueprint)
