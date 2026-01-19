#!/usr/bin/env python3
"""
Migrate training examples to canonical blueprint format.

This script converts training examples from the old schema (vpc_mode, etc.)
to the canonical schema (vpc_env, status fields, etc.) that matches
the actual project blueprint structure.

Usage:
    python tools/migrate_training_to_canonical.py
    python tools/migrate_training_to_canonical.py --backup
    python tools/migrate_training_to_canonical.py --dry-run
"""

import json
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from storage import create_empty_blueprint


def migrate_network(old_network: Dict[str, Any]) -> Dict[str, Any]:
    """Convert old network format to canonical format."""
    canonical = {
        "vpc_id": None,
        "subnet_id": None,
        "security_group_id": None,
        "vpc_env": "dev",  # default
        "rules": old_network.get("rules", []),
        "status": "pending"
    }
    
    # Convert vpc_mode to vpc_env
    vpc_mode = old_network.get("vpc_mode")
    if vpc_mode == "default":
        canonical["vpc_env"] = "prod"
    elif vpc_mode == "new":
        canonical["vpc_env"] = "dev"
    elif "vpc_env" in old_network:
        canonical["vpc_env"] = old_network["vpc_env"]
    
    # Keep subnet_type if present (it's in canonical)
    if "subnet_type" in old_network:
        canonical["subnet_type"] = old_network["subnet_type"]
    
    return canonical


def migrate_compute(old_compute: Dict[str, Any]) -> Dict[str, Any]:
    """Convert old compute format to canonical format."""
    canonical = {
        "instance_type": old_compute.get("instance_type", "t3.micro"),
        "image_id": old_compute.get("image_id"),
        "user_data": old_compute.get("user_data", ""),
        "instance_id": None,
        "status": "pending"
    }
    
    # Keep image_name if present (it's in canonical)
    if "image_name" in old_compute:
        canonical["image_name"] = old_compute["image_name"]
    
    return canonical


def migrate_data(old_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert old data format to canonical format."""
    canonical = {
        "db": {
            "engine": None,
            "instance_class": None,
            "allocated_storage_gb": None,
            "username": None,
            "password": None,
            "endpoint": None,
            "status": "skipped"
        },
        "s3_bucket": {
            "name": None,
            "arn": None,
            "status": "skipped"
        }
    }
    
    # Migrate database
    old_db = old_data.get("db")
    if old_db and old_db is not None:
        if isinstance(old_db, dict):
            canonical["db"].update({
                "engine": old_db.get("engine"),
                "instance_class": old_db.get("instance_class"),
                "allocated_storage_gb": old_db.get("allocated_storage_gb"),
                "username": old_db.get("username"),
                "password": None,
                "endpoint": None,
                "status": "pending" if old_db.get("engine") else "skipped"
            })
    
    # Migrate S3 bucket
    old_s3 = old_data.get("s3_bucket")
    if old_s3 and old_s3 is not None:
        if isinstance(old_s3, dict) and old_s3.get("name"):
            canonical["s3_bucket"] = {
                "name": old_s3.get("name"),
                "arn": None,
                "status": "pending"
            }
    
    return canonical


def migrate_security(old_security: Dict[str, Any]) -> Dict[str, Any]:
    """Convert old security format to canonical format."""
    canonical = {
        "key_pair": {
            "name": None,
            "key_pair_id": None,
            "private_key_pem": None,
            "status": "pending"
        },
        "certificate": {
            "domain": None,
            "cert_arn": None,
            "status": "skipped"
        },
        "iam_role": {
            "role_name": None,
            "policy_document": {},
            "arn": None,
            "instance_profile_arn": None,
            "status": "pending"
        }
    }
    
    # Migrate key_pair
    old_key_pair = old_security.get("key_pair", {})
    if old_key_pair:
        mode = old_key_pair.get("mode", "none")
        canonical["key_pair"] = {
            "name": old_key_pair.get("name"),
            "mode": mode,  # Keep mode for compatibility
            "key_pair_id": None,
            "private_key_pem": None,
            "status": "pending" if mode != "none" else "skipped"
        }
    
    # Migrate certificate
    old_cert = old_security.get("certificate", {})
    if old_cert:
        mode = old_cert.get("mode", "skip")
        canonical["certificate"] = {
            "domain": old_cert.get("domain"),
            "mode": mode,  # Keep mode for compatibility
            "cert_arn": None,
            "status": "pending" if mode != "skip" else "skipped"
        }
    
    # Migrate IAM role
    old_iam = old_security.get("iam_role", {})
    if old_iam:
        enabled = old_iam.get("enabled", False)
        canonical["iam_role"] = {
            "role_name": old_iam.get("role_name"),
            "policy_document": old_iam.get("policy_document", {}),
            "arn": None,
            "instance_profile_arn": None,
            "status": "pending" if enabled else "skipped"
        }
    
    return canonical


def migrate_project(old_project: Dict[str, Any]) -> Dict[str, Any]:
    """Convert old project format to canonical format."""
    canonical = {
        "name": old_project.get("name", ""),
        "description": old_project.get("description", ""),
        "region": old_project.get("region", "us-east-1"),
        "created_at": old_project.get("created_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "owner": old_project.get("owner", ""),
        "cost": old_project.get("cost")
    }
    return canonical


def migrate_blueprint(old_blueprint: Dict[str, Any]) -> Dict[str, Any]:
    """Convert old blueprint format to canonical format."""
    canonical = {
        "project": migrate_project(old_blueprint.get("project", {})),
        "network": migrate_network(old_blueprint.get("network", {})),
        "compute": migrate_compute(old_blueprint.get("compute", {})),
        "data": migrate_data(old_blueprint.get("data", {})),
        "security": migrate_security(old_blueprint.get("security", {}))
    }
    return canonical


def migrate_training_file(json_file: Path, dry_run: bool = False) -> bool:
    """Migrate a single training JSON file to canonical format."""
    try:
        old_data = json.loads(json_file.read_text(encoding="utf-8"))
        new_data = migrate_blueprint(old_data)
        
        if dry_run:
            print(f"  [DRY RUN] Would migrate: {json_file.name}")
            return True
        
        # Write back the migrated data
        json_file.write_text(
            json.dumps(new_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )
        return True
    except Exception as e:
        print(f"  ❌ Error migrating {json_file.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Migrate training examples to canonical blueprint format"
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=Path("data/training"),
        help="Training data directory (default: data/training)"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup before migrating"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    
    args = parser.parse_args()
    
    if not args.training_dir.exists():
        print(f"❌ Training directory does not exist: {args.training_dir}")
        sys.exit(1)
    
    # Find all JSON files
    json_files = sorted(args.training_dir.glob("*.json"))
    
    if not json_files:
        print(f"❌ No JSON files found in {args.training_dir}")
        sys.exit(1)
    
    print(f"📚 Found {len(json_files)} training examples\n")
    
    # Create backup if requested
    if args.backup and not args.dry_run:
        backup_dir = args.training_dir.parent / f"{args.training_dir.name}.backup"
        if backup_dir.exists():
            print(f"⚠️  Backup directory already exists: {backup_dir}")
            response = input("Overwrite? (y/N): ")
            if response.lower() != 'y':
                print("❌ Aborted")
                sys.exit(1)
            shutil.rmtree(backup_dir)
        
        print(f"📦 Creating backup to {backup_dir}...")
        shutil.copytree(args.training_dir, backup_dir)
        print("✅ Backup created\n")
    
    # Migrate files
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Migrating {len(json_files)} files...")
    success_count = 0
    
    for json_file in json_files:
        if migrate_training_file(json_file, dry_run=args.dry_run):
            success_count += 1
    
    print(f"\n✅ Migrated {success_count}/{len(json_files)} files successfully")
    
    if not args.dry_run and success_count == len(json_files):
        print("\n💡 Next step: Regenerate the JSONL file:")
        print("   python tools/convert_to_finetuning_format.py --format unsloth")


if __name__ == "__main__":
    main()
