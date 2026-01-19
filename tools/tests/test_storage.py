"""
Tests for the filesystem storage module.
"""

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage import (
    init_storage,
    slugify,
    save_project,
    load_project,
    list_projects,
    delete_project,
    create_empty_blueprint,
)


def test_slugify():
    """Test slug generation from project names."""
    print("Testing slugify...")
    
    assert slugify("Brenden's Blog") == "brendens-blog"
    assert slugify("My AWS Project") == "my-aws-project"
    assert slugify("test_project_name") == "test-project-name"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"
    assert slugify("Special@#$Characters!") == "specialcharacters"
    assert slugify("") == "unnamed-project"
    assert slugify("123-numbers-456") == "123-numbers-456"
    
    print("  ✓ All slugify tests passed")


def test_init_storage():
    """Test storage directory initialization."""
    print("Testing init_storage...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / "projects"
        training_dir = Path(tmpdir) / "training"
        
        # Directories shouldn't exist yet
        assert not projects_dir.exists()
        assert not training_dir.exists()
        
        # Initialize storage
        p_path, t_path = init_storage(projects_dir, training_dir)
        
        # Now they should exist
        assert p_path.exists()
        assert t_path.exists()
        assert p_path == projects_dir
        assert t_path == training_dir
    
    print("  ✓ All init_storage tests passed")


def test_create_empty_blueprint():
    """Test empty blueprint creation."""
    print("Testing create_empty_blueprint...")
    
    blueprint = create_empty_blueprint(
        name="Test Project",
        description="A test project",
        region="us-west-2",
        owner="tester"
    )
    
    # Check structure
    assert "project" in blueprint
    assert "network" in blueprint
    assert "compute" in blueprint
    assert "data" in blueprint
    assert "security" in blueprint
    
    # Check project section
    assert blueprint["project"]["name"] == "Test Project"
    assert blueprint["project"]["description"] == "A test project"
    assert blueprint["project"]["region"] == "us-west-2"
    assert blueprint["project"]["owner"] == "tester"
    assert "created_at" in blueprint["project"]
    
    # Check defaults
    assert blueprint["compute"]["instance_type"] == "t3.micro"
    assert blueprint["network"]["status"] == "pending"
    assert blueprint["data"]["db"]["status"] == "skipped"
    
    print("  ✓ All create_empty_blueprint tests passed")


def test_save_and_load_project():
    """Test saving and loading a project."""
    print("Testing save_project and load_project...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / "projects"
        projects_dir.mkdir()
        
        # Create a project
        blueprint = create_empty_blueprint(
            name="My Test Project",
            description="Testing save/load",
            region="eu-west-1"
        )
        
        # Add some custom data
        blueprint["compute"]["instance_type"] = "t3.small"
        blueprint["network"]["rules"] = [
            {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"}
        ]
        
        # Save it
        saved_path = save_project(blueprint, projects_dir)
        
        assert saved_path.exists()
        assert saved_path.name == "my-test-project.json"
        
        # Load it back
        loaded = load_project("my-test-project", projects_dir)
        
        assert loaded is not None
        assert loaded["project"]["name"] == "My Test Project"
        assert loaded["compute"]["instance_type"] == "t3.small"
        assert len(loaded["network"]["rules"]) == 1
        
        # Test loading non-existent project
        missing = load_project("does-not-exist", projects_dir)
        assert missing is None
    
    print("  ✓ All save_project and load_project tests passed")


def test_list_projects():
    """Test listing projects."""
    print("Testing list_projects...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / "projects"
        projects_dir.mkdir()
        
        # Initially empty
        projects = list_projects(projects_dir)
        assert len(projects) == 0
        
        # Create some projects
        for i, name in enumerate(["Alpha Project", "Beta Project", "Gamma Project"]):
            blueprint = create_empty_blueprint(name=name, description=f"Project {i+1}")
            save_project(blueprint, projects_dir)
        
        # List them
        projects = list_projects(projects_dir)
        
        assert len(projects) == 3
        
        # Check they're sorted (by filename)
        slugs = [p["slug"] for p in projects]
        assert slugs == ["alpha-project", "beta-project", "gamma-project"]
        
        # Check summary fields
        alpha = next(p for p in projects if p["slug"] == "alpha-project")
        assert alpha["name"] == "Alpha Project"
        assert alpha["status"] == "pending"  # Default status
    
    print("  ✓ All list_projects tests passed")


def test_delete_project():
    """Test deleting a project."""
    print("Testing delete_project...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / "projects"
        projects_dir.mkdir()
        
        # Create a project
        blueprint = create_empty_blueprint(name="To Be Deleted")
        save_project(blueprint, projects_dir)
        
        # Verify it exists
        assert load_project("to-be-deleted", projects_dir) is not None
        
        # Delete it
        result = delete_project("to-be-deleted", projects_dir)
        assert result is True
        
        # Verify it's gone
        assert load_project("to-be-deleted", projects_dir) is None
        
        # Deleting again should return False
        result = delete_project("to-be-deleted", projects_dir)
        assert result is False
    
    print("  ✓ All delete_project tests passed")


def test_project_json_structure():
    """Verify the JSON structure matches the canonical schema from the plan."""
    print("Testing project JSON structure against canonical schema...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / "projects"
        projects_dir.mkdir()
        
        # Create and save a full project
        blueprint = create_empty_blueprint(
            name="brendens-blog",
            description="Personal static site + small Postgres backend",
            region="us-east-2",
            owner="brenden"
        )
        
        # Fill in some data to match the canonical example
        blueprint["network"]["rules"] = [
            {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"},
            {"port": 443, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTPS"}
        ]
        blueprint["compute"]["instance_type"] = "t3.micro"
        blueprint["compute"]["image_id"] = "ami-0abcdef1234567890"
        blueprint["compute"]["user_data"] = "#!/bin/bash\napt update && apt install -y nginx"
        
        save_project(blueprint, projects_dir)
        
        # Read raw JSON to verify structure
        with open(projects_dir / "brendens-blog.json", 'r') as f:
            raw = json.load(f)
        
        # Verify top-level keys
        expected_keys = {"project", "network", "compute", "data", "security"}
        assert set(raw.keys()) == expected_keys, f"Unexpected keys: {set(raw.keys())}"
        
        # Verify project section
        assert all(k in raw["project"] for k in ["name", "description", "region", "created_at", "owner"])
        
        # Verify network section
        assert all(k in raw["network"] for k in ["vpc_id", "subnet_id", "security_group_id", "rules", "status"])
        
        # Verify compute section
        assert all(k in raw["compute"] for k in ["instance_type", "image_id", "user_data", "instance_id", "status"])
        
        # Verify data section
        assert "db" in raw["data"]
        assert "s3_bucket" in raw["data"]
        
        # Verify security section
        assert all(k in raw["security"] for k in ["key_pair", "certificate", "iam_role"])
    
    print("  ✓ JSON structure matches canonical schema")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Pockitect Storage Module Tests")
    print("="*60 + "\n")
    
    test_slugify()
    test_init_storage()
    test_create_empty_blueprint()
    test_save_and_load_project()
    test_list_projects()
    test_delete_project()
    test_project_json_structure()
    
    print("\n" + "="*60)
    print("All tests passed! ✓")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
