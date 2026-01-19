"""
Tests for the Deployment Orchestrator.

These tests use mocking to avoid actual AWS API calls.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import time

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aws.deploy import (
    DeploymentOrchestrator,
    DeploymentStatus,
    DeploymentState,
    DeploymentStep,
    StepStatus,
    StatusPoller,
)
from aws.resources import ResourceResult


def create_test_blueprint():
    """Create a test blueprint for testing."""
    return {
        "project": {
            "name": "test-project",
            "description": "Test project",
            "region": "us-east-1",
            "owner": "tester"
        },
        "network": {
            "vpc_id": None,
            "subnet_id": None,
            "security_group_id": None,
            "vpc_mode": "default",
            "rules": [
                {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"}
            ],
            "status": "pending"
        },
        "compute": {
            "instance_type": "t3.micro",
            "image_id": "ami-12345678",
            "user_data": "",
            "instance_id": None,
            "status": "pending"
        },
        "data": {
            "db": {"status": "skipped"},
            "s3_bucket": {"status": "skipped"}
        },
        "security": {
            "key_pair": {
                "mode": "generate",
                "name": "test-key",
                "status": "pending"
            },
            "iam_role": {
                "enabled": True,
                "role_name": "test-role",
                "status": "pending"
            }
        }
    }


def test_deployment_step_status():
    """Test DeploymentStep status tracking."""
    print("Testing DeploymentStep status...")
    
    step = DeploymentStep(
        name="test_step",
        description="Test step"
    )
    
    assert step.status == StepStatus.PENDING
    assert step.resource_id is None
    assert step.error is None
    assert step.started_at is None
    assert step.completed_at is None
    
    print("  ✓ DeploymentStep status test passed")


def test_deployment_state():
    """Test DeploymentState initialization."""
    print("Testing DeploymentState...")
    
    state = DeploymentState()
    
    assert state.status == DeploymentStatus.PENDING
    assert state.steps == []
    assert state.current_step == 0
    assert state.started_at is None
    assert state.completed_at is None
    assert state.error is None
    
    print("  ✓ DeploymentState test passed")


def test_orchestrator_init_steps():
    """Test that orchestrator initializes correct steps from blueprint."""
    print("Testing orchestrator step initialization...")
    
    blueprint = create_test_blueprint()
    orchestrator = DeploymentOrchestrator(blueprint)
    
    # Should have: get_default_vpc, create_security_group, create_key_pair, 
    # create_iam_role, launch_instance, verify_deployment
    step_names = [s.name for s in orchestrator.state.steps]
    
    assert "get_default_vpc" in step_names
    assert "create_security_group" in step_names
    assert "create_key_pair" in step_names
    assert "create_iam_role" in step_names
    assert "launch_instance" in step_names
    assert "verify_deployment" in step_names
    
    # Should NOT have database/s3 steps (skipped in blueprint)
    assert "create_database" not in step_names
    assert "create_bucket" not in step_names
    
    print("  ✓ Orchestrator step initialization test passed")


def test_orchestrator_init_steps_with_db():
    """Test orchestrator includes database step when enabled."""
    print("Testing orchestrator with database enabled...")
    
    blueprint = create_test_blueprint()
    blueprint["data"]["db"] = {
        "engine": "postgres",
        "instance_class": "db.t3.micro",
        "allocated_storage_gb": 20,
        "username": "admin",
        "status": "pending"
    }
    
    orchestrator = DeploymentOrchestrator(blueprint, db_password="testpass")
    step_names = [s.name for s in orchestrator.state.steps]
    
    assert "create_database" in step_names
    
    print("  ✓ Orchestrator with database test passed")


def test_orchestrator_init_steps_with_s3():
    """Test orchestrator includes S3 step when enabled."""
    print("Testing orchestrator with S3 enabled...")
    
    blueprint = create_test_blueprint()
    blueprint["data"]["s3_bucket"] = {
        "name": "test-bucket",
        "status": "pending"
    }
    
    orchestrator = DeploymentOrchestrator(blueprint)
    step_names = [s.name for s in orchestrator.state.steps]
    
    assert "create_bucket" in step_names
    
    print("  ✓ Orchestrator with S3 test passed")


def test_orchestrator_cancel():
    """Test deployment cancellation."""
    print("Testing orchestrator cancellation...")
    
    blueprint = create_test_blueprint()
    orchestrator = DeploymentOrchestrator(blueprint)
    
    assert orchestrator._cancel_requested is False
    
    orchestrator.cancel()
    
    assert orchestrator._cancel_requested is True
    
    print("  ✓ Orchestrator cancellation test passed")


@patch.object(DeploymentOrchestrator, '_step_get_default_vpc')
@patch.object(DeploymentOrchestrator, '_step_create_security_group')
@patch.object(DeploymentOrchestrator, '_step_create_key_pair')
@patch.object(DeploymentOrchestrator, '_step_create_iam_role')
@patch.object(DeploymentOrchestrator, '_step_launch_instance')
@patch.object(DeploymentOrchestrator, '_step_verify_deployment')
def test_orchestrator_deploy_success(mock_verify, mock_launch, mock_iam, 
                                      mock_key, mock_sg, mock_vpc):
    """Test successful deployment flow."""
    print("Testing successful deployment flow...")
    
    # Mock all steps to succeed
    mock_vpc.return_value = ResourceResult(success=True, resource_id="vpc-123")
    mock_sg.return_value = ResourceResult(success=True, resource_id="sg-123")
    mock_key.return_value = ResourceResult(success=True, resource_id="key-123")
    mock_iam.return_value = ResourceResult(success=True, resource_id="role-123")
    mock_launch.return_value = ResourceResult(success=True, resource_id="i-123")
    mock_verify.return_value = ResourceResult(success=True)
    
    blueprint = create_test_blueprint()
    orchestrator = DeploymentOrchestrator(blueprint)
    
    # Track progress callbacks
    progress_calls = []
    def on_progress(state):
        progress_calls.append(state.status)
    
    result = orchestrator.deploy(on_progress=on_progress)
    
    assert result is True
    assert orchestrator.state.status == DeploymentStatus.COMPLETED
    assert all(s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] 
               for s in orchestrator.state.steps)
    
    # Verify progress was reported
    assert DeploymentStatus.IN_PROGRESS in progress_calls
    assert DeploymentStatus.COMPLETED in progress_calls
    
    print("  ✓ Successful deployment flow test passed")


@patch.object(DeploymentOrchestrator, '_step_get_default_vpc')
@patch.object(DeploymentOrchestrator, '_step_create_security_group')
def test_orchestrator_deploy_failure(mock_sg, mock_vpc):
    """Test deployment failure handling."""
    print("Testing deployment failure handling...")
    
    # First step succeeds, second fails
    mock_vpc.return_value = ResourceResult(success=True, resource_id="vpc-123")
    mock_sg.return_value = ResourceResult(success=False, error="Permission denied")
    
    blueprint = create_test_blueprint()
    orchestrator = DeploymentOrchestrator(blueprint)
    
    result = orchestrator.deploy()
    
    assert result is False
    assert orchestrator.state.status == DeploymentStatus.FAILED
    assert orchestrator.state.error == "Permission denied"
    
    # First step should be completed, second failed
    assert orchestrator.state.steps[0].status == StepStatus.COMPLETED
    assert orchestrator.state.steps[1].status == StepStatus.FAILED
    
    print("  ✓ Deployment failure handling test passed")


def test_orchestrator_get_updated_blueprint():
    """Test getting updated blueprint after deployment."""
    print("Testing get_updated_blueprint...")
    
    blueprint = create_test_blueprint()
    orchestrator = DeploymentOrchestrator(blueprint)
    
    # Manually update the blueprint
    orchestrator.blueprint['network']['vpc_id'] = 'vpc-test'
    orchestrator.blueprint['compute']['instance_id'] = 'i-test'
    
    updated = orchestrator.get_updated_blueprint()
    
    assert updated['network']['vpc_id'] == 'vpc-test'
    assert updated['compute']['instance_id'] == 'i-test'
    
    print("  ✓ get_updated_blueprint test passed")


def test_deployment_status_enum():
    """Test DeploymentStatus enum values."""
    print("Testing DeploymentStatus enum...")
    
    assert DeploymentStatus.PENDING.value == "pending"
    assert DeploymentStatus.IN_PROGRESS.value == "in_progress"
    assert DeploymentStatus.COMPLETED.value == "completed"
    assert DeploymentStatus.FAILED.value == "failed"
    assert DeploymentStatus.CANCELLED.value == "cancelled"
    
    print("  ✓ DeploymentStatus enum test passed")


def test_step_status_enum():
    """Test StepStatus enum values."""
    print("Testing StepStatus enum...")
    
    assert StepStatus.PENDING.value == "pending"
    assert StepStatus.IN_PROGRESS.value == "in_progress"
    assert StepStatus.COMPLETED.value == "completed"
    assert StepStatus.FAILED.value == "failed"
    assert StepStatus.SKIPPED.value == "skipped"
    
    print("  ✓ StepStatus enum test passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Deployment Orchestrator Tests")
    print("="*60 + "\n")
    
    test_deployment_step_status()
    test_deployment_state()
    test_orchestrator_init_steps()
    test_orchestrator_init_steps_with_db()
    test_orchestrator_init_steps_with_s3()
    test_orchestrator_cancel()
    test_orchestrator_deploy_success()
    test_orchestrator_deploy_failure()
    test_orchestrator_get_updated_blueprint()
    test_deployment_status_enum()
    test_step_status_enum()
    
    print("\n" + "="*60)
    print("All deployment orchestrator tests passed! ✓")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
