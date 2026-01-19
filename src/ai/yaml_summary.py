"""Utilities to summarize YAML blueprints for display."""

from __future__ import annotations

from typing import Dict, Any, List


def summarize_blueprint(blueprint: Dict[str, Any]) -> str:
    project = blueprint.get("project", {})
    network = blueprint.get("network", {})
    compute = blueprint.get("compute", {})
    data = blueprint.get("data", {})
    security = blueprint.get("security", {})

    title = project.get("name") or "Unnamed project"
    region = project.get("region") or "unknown region"
    description = project.get("description") or ""

    lines: List[str] = [f"Project: {title} ({region})"]
    if description:
        lines.append(f"Description: {description}")

    instance_type = compute.get("instance_type")
    image_id = compute.get("image_id")
    if instance_type or image_id:
        detail = instance_type or "unspecified"
        if image_id:
            detail = f"{detail} ({image_id})"
        lines.append(f"Compute: {detail}")

    db = data.get("db", {}) if isinstance(data, dict) else {}
    if isinstance(db, dict) and db.get("engine"):
        db_line = f"Database: {db.get('engine')}"
        if db.get("instance_class"):
            db_line += f" ({db.get('instance_class')})"
        if db.get("allocated_storage_gb"):
            db_line += f", {db.get('allocated_storage_gb')}GB"
        lines.append(db_line)

    s3 = data.get("s3_bucket", {}) if isinstance(data, dict) else {}
    if isinstance(s3, dict) and s3.get("name"):
        lines.append(f"S3 Bucket: {s3.get('name')}")

    key_pair = security.get("key_pair", {}) if isinstance(security, dict) else {}
    if isinstance(key_pair, dict) and key_pair.get("name"):
        lines.append(f"SSH Key: {key_pair.get('name')} ({key_pair.get('mode', 'generate')})")

    rules = network.get("rules", []) if isinstance(network, dict) else []
    if rules:
        ports = sorted({str(rule.get("port")) for rule in rules if rule.get("port")})
        if ports:
            lines.append(f"Open Ports: {', '.join(ports)}")

    return "\n".join(lines)
