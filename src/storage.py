"""
Filesystem-based project storage for Pockitect MVP.

This module handles all persistence of project blueprints as YAML files.
Projects are stored in ./data/projects/<slug>.yaml
Training pairs are stored in ./data/training/<NNN>-<name>.json + .prompt.txt
"""

import json
import yaml
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterable

from app.core.project_status import ProjectStatusCalculator

# Default paths relative to workspace root
DEFAULT_PROJECTS_DIR = Path("data/projects")
DEFAULT_TRAINING_DIR = Path("data/training") # Keep training here for now or move to data/training? User didn't specify. Assuming keep or move? User said "data dir, to put projects, examples, logs". I'll leave training for now or better, move it to data/training for consistency.
DEFAULT_CACHE_DIR = Path("data/cache")
PROJECT_REGIONS_CACHE = DEFAULT_CACHE_DIR / "project_regions.json"



def get_workspace_root() -> Path:
    """
    Get the workspace root directory.
    For MVP, this is the directory containing the 'projects' folder.
    """
    # Start from this file's location and go up to find workspace root
    current = Path(__file__).resolve().parent.parent
    return current


def init_storage(
    projects_dir: Optional[Path] = None,
    training_dir: Optional[Path] = None
) -> tuple[Path, Path]:
    """
    Ensure storage directories exist.
    
    Args:
        projects_dir: Custom projects directory (default: ./projects/)
        training_dir: Custom training directory (default: ./training/)
    
    Returns:
        Tuple of (projects_path, training_path) as absolute paths
    """
    root = get_workspace_root()
    
    projects_path = projects_dir or (root / DEFAULT_PROJECTS_DIR)
    training_path = training_dir or (root / DEFAULT_TRAINING_DIR)
    
    projects_path.mkdir(parents=True, exist_ok=True)
    training_path.mkdir(parents=True, exist_ok=True)
    
    return projects_path, training_path


def slugify(name: str) -> str:
    """
    Convert a project name to a filesystem-safe slug.
    
    Args:
        name: The project name (e.g., "Brenden's Blog")
    
    Returns:
        A slug (e.g., "brendens-blog")
    """
    # Lowercase
    slug = name.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    # Remove non-alphanumeric characters (except hyphens)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    
    return slug or "unnamed-project"


def get_project_path(slug: str, projects_dir: Optional[Path] = None) -> Path:
    """
    Get the full path for a project YAML file.
    
    Args:
        slug: The project slug
        projects_dir: Custom projects directory
    
    Returns:
        Full path to the project YAML file
    """
    root = get_workspace_root()
    projects_path = projects_dir or (root / DEFAULT_PROJECTS_DIR)
    return projects_path / f"{slug}.yaml"


def save_project(project_data: dict, projects_dir: Optional[Path] = None) -> Path:
    """
    Save a project blueprint to disk.
    
    The project must have a 'project.name' field. A slug is auto-generated
    from the name if not already present.
    
    Args:
        project_data: The project blueprint dictionary
        projects_dir: Custom projects directory
    
    Returns:
        Path to the saved YAML file
    
    Raises:
        ValueError: If project_data is missing required fields
    """
    if "project" not in project_data:
        raise ValueError("project_data must contain a 'project' section")
    
    project_info = project_data["project"]
    
    if "name" not in project_info:
        raise ValueError("project.name is required")
    
    # Generate slug from name
    slug = slugify(project_info["name"])
    
    # Add metadata if not present
    if "created_at" not in project_info:
        project_info["created_at"] = datetime.utcnow().isoformat() + "Z"
    
    # Get the file path
    file_path = get_project_path(slug, projects_dir)
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write YAML
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(project_data, f, default_flow_style=False, sort_keys=False)
    
    # Refresh cached regions for faster targeted scans
    write_project_regions_cache(projects_dir=projects_dir)
    
    return file_path


def load_project(slug: str, projects_dir: Optional[Path] = None) -> Optional[dict]:
    """
    Load a project blueprint from disk.
    
    Args:
        slug: The project slug (filename without .yaml)
        projects_dir: Custom projects directory
    
    Returns:
        The project blueprint dictionary, or None if not found
    """
    file_path = get_project_path(slug, projects_dir)
    
    if not file_path.exists():
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def list_projects(projects_dir: Optional[Path] = None) -> list[dict]:
    """
    List all projects in the projects directory.
    
    Returns a list of summary dictionaries with basic info about each project.
    
    Args:
        projects_dir: Custom projects directory
    
    Returns:
        List of project summaries: [{"slug": "...", "name": "...", "status": "...", "path": "..."}]
    """
    root = get_workspace_root()
    projects_path = projects_dir or (root / DEFAULT_PROJECTS_DIR)
    
    if not projects_path.exists():
        return []
    
    projects = []
    
    for file_path in sorted(projects_path.glob("*.yaml")):
        slug = file_path.stem
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            project_info = data.get("project", {})
            
            overall_status = ProjectStatusCalculator.calculate_status_from_blueprint(data)
            
            projects.append({
                "slug": slug,
                "name": project_info.get("name", slug),
                "description": project_info.get("description", ""),
                "region": project_info.get("region", ""),
                "created_at": project_info.get("created_at", ""),
                "cost": project_info.get("cost"),
                "status": overall_status,
                "path": str(file_path)
            })
        except (yaml.YAMLError, KeyError) as e:
            # Include broken projects with error status
            projects.append({
                "slug": slug,
                "name": slug,
                "description": f"Error loading: {e}",
                "region": "",
                "created_at": "",
                "status": "error",
                "path": str(file_path)
            })
    
    return projects


def delete_project(slug: str, projects_dir: Optional[Path] = None) -> bool:
    """
    Delete a project from disk.
    
    Args:
        slug: The project slug
        projects_dir: Custom projects directory
    
    Returns:
        True if deleted, False if not found
    """
    file_path = get_project_path(slug, projects_dir)
    
    if not file_path.exists():
        return False
    
    file_path.unlink()
    # Refresh cached regions for faster targeted scans
    write_project_regions_cache(projects_dir=projects_dir)
    return True


def _project_regions_cache_path(cache_dir: Optional[Path] = None) -> Path:
    root = get_workspace_root()
    return (cache_dir or (root / DEFAULT_CACHE_DIR)) / "project_regions.json"


def get_project_regions(projects_dir: Optional[Path] = None) -> list[str]:
    regions = set()
    for project in list_projects(projects_dir):
        region = (project.get("region") or "").strip()
        if region:
            regions.add(region)
    return sorted(regions)


def write_project_regions_cache(
    regions: Optional[Iterable[str]] = None,
    projects_dir: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
) -> list[str]:
    if regions is None:
        regions = get_project_regions(projects_dir)
    payload = {"regions": sorted({r for r in regions if r})}
    cache_path = _project_regions_cache_path(cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload["regions"]


def load_project_regions_cache(cache_dir: Optional[Path] = None) -> list[str]:
    cache_path = _project_regions_cache_path(cache_dir)
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        regions = payload.get("regions") or []
        if isinstance(regions, list):
            return [r for r in regions if isinstance(r, str) and r]
        return []
    except Exception:
        return []


def create_empty_blueprint(
    name: str,
    description: str = "",
    region: str = "us-east-1",
    owner: str = ""
) -> dict:
    """
    Create an empty project blueprint with the canonical structure.
    
    This is useful for initializing a new project before the wizard fills in details.
    
    Args:
        name: Project name
        description: Short description
        region: AWS region
        owner: Project owner name
    
    Returns:
        A complete blueprint dictionary with all sections initialized to defaults
    """
    return {
        "project": {
            "name": name,
            "description": description,
            "region": region,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "owner": owner,
            "cost": None
        },
        "network": {
            "vpc_id": None,
            "subnet_id": None,
            "security_group_id": None,
            "vpc_env": "dev",
            "rules": [],
            "status": "pending"
        },
        "compute": {
            "instance_type": "t3.micro",
            "image_id": None,
            "user_data": "",
            "instance_id": None,
            "status": "pending"
        },
        "data": {
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
        },
        "security": {
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
    }
