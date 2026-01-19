#!/usr/bin/env python3
"""
Normalize training JSON files to canonical blueprint schema.

Fixes:
- data.db should be an object (not null)
- data.s3_bucket should be an object (not null)
- removes security.iam_role.enabled
- fills missing status/metadata fields using create_empty_blueprint
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from storage import create_empty_blueprint


def merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in src.items():
        if isinstance(value, dict):
            node = dst.get(key)
            if isinstance(node, dict):
                merge(node, value)
            else:
                dst[key] = value
        else:
            if value is not None:
                dst[key] = value
    return dst


def normalize_blueprint(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    project = blueprint.get("project", {})
    name = project.get("name") or "Untitled Project"
    description = project.get("description") or ""
    region = project.get("region") or "us-east-1"
    owner = project.get("owner") or ""

    base = create_empty_blueprint(name, description, region, owner)
    normalized = merge(base, blueprint)

    # Ensure db and s3_bucket are objects, not null.
    data = normalized.setdefault("data", {})
    if data.get("db") is None:
        data["db"] = base["data"]["db"]
    if data.get("s3_bucket") is None:
        data["s3_bucket"] = base["data"]["s3_bucket"]

    # Remove iam_role.enabled if present.
    security = normalized.get("security", {})
    iam_role = security.get("iam_role", {})
    if "enabled" in iam_role:
        iam_role.pop("enabled", None)

    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize training JSON to canonical schema.")
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=Path("data/training"),
        help="Training data directory (default: data/training)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print files that would change.")
    args = parser.parse_args()

    if not args.training_dir.exists():
        print(f"Training directory does not exist: {args.training_dir}")
        sys.exit(1)

    json_files = sorted(args.training_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {args.training_dir}")
        sys.exit(1)

    changed = 0
    for json_file in json_files:
        raw = json_file.read_text(encoding="utf-8")
        original = json.loads(raw)
        normalized = normalize_blueprint(original)

        if normalized != original:
            changed += 1
            if args.dry_run:
                print(f"Would update: {json_file.name}")
            else:
                json_file.write_text(
                    json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

    print(f"Normalized {changed} file(s).")


if __name__ == "__main__":
    main()
