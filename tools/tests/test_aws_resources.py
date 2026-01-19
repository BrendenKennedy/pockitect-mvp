"""
Tests for the AWS Resource Manager.

These tests use mocking to avoid actual AWS API calls.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aws.resources import AWSResourceManager, ResourceResult


def test_resource_result_success():
    """Test ResourceResult for successful operations."""
    print("Testing ResourceResult success case...")
    
    result = ResourceResult(
        success=True,
        resource_id="vpc-12345",
        arn="arn:aws:ec2:us-east-1:123456789:vpc/vpc-12345",
        data={'extra': 'info'}
    )
    
    assert result.success is True
    assert result.resource_id == "vpc-12345"
    assert result.arn is not None
    assert result.error is None
    assert result.data['extra'] == 'info'
    
    print("  ✓ ResourceResult success test passed")


def test_resource_result_failure():
    """Test ResourceResult for failed operations."""
    print("Testing ResourceResult failure case...")
    
    result = ResourceResult(
        success=False,
        error="Something went wrong"
    )
    
    assert result.success is False
    assert result.resource_id is None
    assert result.error == "Something went wrong"
    
    print("  ✓ ResourceResult failure test passed")


def test_resource_manager_initialization():
    """Test AWSResourceManager initialization."""
    print("Testing AWSResourceManager initialization...")
    
    manager = AWSResourceManager(region="us-east-1")
    
    assert manager.region == "us-east-1"
    assert manager._ec2 is None  # Lazy loaded
    assert manager._rds is None
    assert manager._s3 is None
    assert manager._iam is None
    
    print("  ✓ AWSResourceManager initialization test passed")


@patch('boto3.client')
def test_get_default_vpc(mock_boto_client):
    """Test getting default VPC."""
    print("Testing get_default_vpc...")
    
    mock_ec2 = MagicMock()
    mock_ec2.describe_vpcs.return_value = {
        'Vpcs': [{
            'VpcId': 'vpc-default123',
            'IsDefault': True,
            'CidrBlock': '172.31.0.0/16'
        }]
    }
    mock_ec2.describe_subnets.return_value = {
        'Subnets': [{
            'SubnetId': 'subnet-default123',
            'VpcId': 'vpc-default123',
            'DefaultForAz': True
        }]
    }
    mock_boto_client.return_value = mock_ec2
    
    manager = AWSResourceManager(region="us-east-1")
    result = manager.get_default_vpc()
    
    assert result.success is True
    assert result.resource_id == 'vpc-default123'
    assert result.data['subnet_id'] == 'subnet-default123'
    
    print("  ✓ get_default_vpc test passed")


@patch('boto3.client')
def test_create_security_group(mock_boto_client):
    """Test creating a security group."""
    print("Testing create_security_group...")
    
    mock_ec2 = MagicMock()
    mock_ec2.create_security_group.return_value = {
        'GroupId': 'sg-12345678'
    }
    mock_boto_client.return_value = mock_ec2
    
    manager = AWSResourceManager(region="us-east-1")
    result = manager.create_security_group(
        vpc_id="vpc-12345",
        name="test-sg",
        description="Test security group",
        rules=[
            {"port": 22, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "SSH"},
            {"port": 80, "protocol": "tcp", "cidr": "0.0.0.0/0", "description": "HTTP"},
        ]
    )
    
    assert result.success is True
    assert result.resource_id == 'sg-12345678'
    
    # Verify authorize_security_group_ingress was called
    mock_ec2.authorize_security_group_ingress.assert_called_once()
    
    print("  ✓ create_security_group test passed")


@patch('boto3.client')
def test_create_key_pair(mock_boto_client):
    """Test creating a key pair."""
    print("Testing create_key_pair...")
    
    mock_ec2 = MagicMock()
    mock_ec2.create_key_pair.return_value = {
        'KeyPairId': 'key-12345678',
        'KeyName': 'test-key',
        'KeyMaterial': '-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n-----END OPENSSH PRIVATE KEY-----'
    }
    mock_boto_client.return_value = mock_ec2
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = AWSResourceManager(region="us-east-1")
        result = manager.create_key_pair(
            name="test-key",
            save_path=Path(tmpdir)
        )
        
        assert result.success is True
        assert result.resource_id == 'key-12345678'
        assert 'key_file' in result.data
        assert Path(result.data['key_file']).exists()
        
        # Check file permissions (should be 600)
        key_file = Path(result.data['key_file'])
        assert (key_file.stat().st_mode & 0o777) == 0o600
    
    print("  ✓ create_key_pair test passed")


@patch('boto3.client')
def test_launch_instance(mock_boto_client):
    """Test launching an EC2 instance."""
    print("Testing launch_instance...")
    
    mock_ec2 = MagicMock()
    mock_ec2.run_instances.return_value = {
        'Instances': [{
            'InstanceId': 'i-1234567890abcdef0'
        }]
    }
    mock_boto_client.return_value = mock_ec2
    
    manager = AWSResourceManager(region="us-east-1")
    result = manager.launch_instance(
        image_id="ami-12345678",
        instance_type="t3.micro",
        subnet_id="subnet-12345",
        security_group_id="sg-12345",
        key_name="my-key",
        user_data="#!/bin/bash\necho hello"
    )
    
    assert result.success is True
    assert result.resource_id == 'i-1234567890abcdef0'
    
    # Verify run_instances was called with correct parameters
    call_args = mock_ec2.run_instances.call_args
    assert call_args.kwargs['ImageId'] == 'ami-12345678'
    assert call_args.kwargs['InstanceType'] == 't3.micro'
    assert call_args.kwargs['KeyName'] == 'my-key'
    
    print("  ✓ launch_instance test passed")


@patch('boto3.client')
def test_get_instance_status(mock_boto_client):
    """Test getting instance status."""
    print("Testing get_instance_status...")
    
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        'Reservations': [{
            'Instances': [{
                'InstanceId': 'i-12345',
                'State': {'Name': 'running'},
                'PublicIpAddress': '54.123.45.67',
                'PrivateIpAddress': '10.0.1.100',
                'PublicDnsName': 'ec2-54-123-45-67.compute-1.amazonaws.com'
            }]
        }]
    }
    mock_boto_client.return_value = mock_ec2
    
    manager = AWSResourceManager(region="us-east-1")
    result = manager.get_instance_status('i-12345')
    
    assert result.success is True
    assert result.data['state'] == 'running'
    assert result.data['public_ip'] == '54.123.45.67'
    assert result.data['private_ip'] == '10.0.1.100'
    
    print("  ✓ get_instance_status test passed")


@patch('boto3.client')
def test_create_bucket(mock_boto_client):
    """Test creating an S3 bucket."""
    print("Testing create_bucket...")
    
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3
    
    manager = AWSResourceManager(region="us-west-2")
    result = manager.create_bucket("my-test-bucket")
    
    assert result.success is True
    assert result.resource_id == "my-test-bucket"
    assert result.arn == "arn:aws:s3:::my-test-bucket"
    
    # Verify bucket was created with location constraint (non us-east-1)
    call_args = mock_s3.create_bucket.call_args
    assert call_args.kwargs['CreateBucketConfiguration']['LocationConstraint'] == 'us-west-2'
    
    # Verify public access block was set
    mock_s3.put_public_access_block.assert_called_once()
    
    print("  ✓ create_bucket test passed")


@patch('boto3.client')
def test_create_db_instance(mock_boto_client):
    """Test creating an RDS instance."""
    print("Testing create_db_instance...")
    
    mock_rds = MagicMock()
    mock_rds.create_db_instance.return_value = {
        'DBInstance': {
            'DBInstanceIdentifier': 'my-db',
            'DBInstanceStatus': 'creating'
        }
    }
    mock_boto_client.return_value = mock_rds
    
    manager = AWSResourceManager(region="us-east-1")
    result = manager.create_db_instance(
        identifier="my-db",
        engine="postgres",
        instance_class="db.t3.micro",
        allocated_storage=20,
        master_username="admin",
        master_password="secretpassword123",
        vpc_security_group_id="sg-12345"
    )
    
    assert result.success is True
    assert result.resource_id == "my-db"
    
    print("  ✓ create_db_instance test passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AWS Resource Manager Tests")
    print("="*60 + "\n")
    
    test_resource_result_success()
    test_resource_result_failure()
    test_resource_manager_initialization()
    test_get_default_vpc()
    test_create_security_group()
    test_create_key_pair()
    test_launch_instance()
    test_get_instance_status()
    test_create_bucket()
    test_create_db_instance()
    
    print("\n" + "="*60)
    print("All resource manager tests passed! ✓")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
