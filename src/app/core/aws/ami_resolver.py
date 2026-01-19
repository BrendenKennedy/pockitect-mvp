import json
from pathlib import Path
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from app.core.config import WORKSPACE_ROOT


class AmiResolver:
    def __init__(self, session, region_name: str):
        self.session = session
        self.region_name = region_name
        self._cache: Dict[str, str] = {}
        self._mapping = self._load_mapping()

    def _load_mapping(self) -> Dict[str, Any]:
        mapping_path = WORKSPACE_ROOT / "data" / "ami_map.json"
        try:
            return json.loads(mapping_path.read_text(encoding="utf-8"))
        except Exception:
            return {"default": None, "images": {}}

    def resolve(self, image_id: Optional[str]) -> Optional[str]:
        if not image_id:
            image_id = self._mapping.get("default")
        if not image_id:
            return None

        if image_id.startswith("ami-"):
            return image_id

        if image_id in self._cache:
            return self._cache[image_id]

        entry = None
        param_name = None

        if image_id.startswith("ssm:"):
            param_name = image_id[len("ssm:") :]
        else:
            entry = (self._mapping.get("images") or {}).get(image_id, {})
            if entry.get("regions"):
                param_name = entry["regions"].get(self.region_name)
            elif entry.get("ssm_parameter"):
                param_name = entry["ssm_parameter"]
            elif entry.get("ec2_filters"):
                param_name = self._resolve_via_ec2(entry)

        if not param_name:
            return image_id

        if param_name.startswith("ami-"):
            resolved = param_name
        else:
            ssm = self.session.client("ssm", region_name=self.region_name)
            try:
                resp = ssm.get_parameter(Name=param_name)
                resolved = resp["Parameter"]["Value"]
            except ClientError:
                # If SSM is not permitted, try EC2 filters if provided.
                if entry and entry.get("ec2_filters"):
                    resolved = self._resolve_via_ec2(entry)
                else:
                    raise

        self._cache[image_id] = resolved
        return resolved

    def _resolve_via_ec2(self, entry: Dict[str, Any]) -> Optional[str]:
        filters = []
        owners = entry.get("ec2_filters", {}).get("owners") or ["amazon"]
        name_pattern = entry.get("ec2_filters", {}).get("name_pattern")
        raw_filters = entry.get("ec2_filters", {}).get("filters") or []
        if name_pattern:
            filters.append({"Name": "name", "Values": [name_pattern]})
        for item in raw_filters:
            if isinstance(item, dict) and item.get("Name") and item.get("Values"):
                filters.append(item)
        if not any(f.get("Name") == "state" for f in filters):
            filters.append({"Name": "state", "Values": ["available"]})

        ec2 = self.session.client("ec2", region_name=self.region_name)
        resp = ec2.describe_images(Owners=owners, Filters=filters)
        images = resp.get("Images") or []
        if not images:
            return None
        images.sort(key=lambda img: img.get("CreationDate", ""), reverse=True)
        return images[0].get("ImageId")
