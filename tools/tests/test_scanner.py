import pytest
import asyncio
from unittest.mock import MagicMock
from datetime import datetime
from app.core.aws.scanner import ResourceScanner
from app.core.config import KEY_ALL_RESOURCES

@pytest.mark.unit
@pytest.mark.asyncio
async def test_scan_all_regions(mock_boto_session, redis_client_wrapper):
    # Setup mocks
    mock_s3 = MagicMock()
    mock_s3.list_buckets.return_value = {
        'Buckets': [{'Name': 'bucket-1', 'CreationDate': datetime(2023, 1, 1)}]
    }
    
    mock_ec2 = MagicMock()
    # Mock EC2 paginator properly
    paginator = MagicMock()
    # Ensure InstanceType is present to avoid KeyError in scanner
    paginator.paginate.return_value = [
        {'Reservations': [{'Instances': [{
            'InstanceId': 'i-123', 
            'InstanceType': 't2.micro',
            'State': {'Name': 'running'}, 
            'Tags': [{'Key': 'Name', 'Value': 'vm-1'}]
        }]}]}
    ]
    mock_ec2.get_paginator.return_value = paginator
    mock_ec2.describe_vpcs.return_value = {'Vpcs': []}
    
    mock_rds = MagicMock()
    mock_rds.describe_db_instances.return_value = {'DBInstances': []}
    
    # Configure session to return appropriate client based on service/region
    def client_side_effect(service, region_name=None):
        if service == 's3': return mock_s3
        if service == 'ec2': return mock_ec2
        if service == 'rds': return mock_rds
        return MagicMock()
        
    mock_boto_session.return_value.client.side_effect = client_side_effect
    
    # Run scan
    scanner = ResourceScanner()
    results = await scanner.scan_all(regions=['us-east-1'])
    
    # Verify results
    # We should have S3 (global) and EC2 (us-east-1)
    assert len(results) >= 2, f"Got {len(results)}: {results}"
    
    bucket = next((r for r in results if r['type'] == 's3_bucket'), None)
    assert bucket is not None
    assert bucket['id'] == 'bucket-1'
    
    vm = next((r for r in results if r['type'] == 'ec2_instance'), None)
    assert vm is not None
    assert vm['id'] == 'i-123'
    
    # Verify Redis update
    redis_data = redis_client_wrapper.hget_all_json(KEY_ALL_RESOURCES)
    assert len(redis_data) >= 2
    assert any("bucket-1" in k for k in redis_data)

@pytest.mark.unit
@pytest.mark.asyncio
async def test_scan_error_handling(mock_boto_session, redis_client_wrapper):
    """Verify that one region failure doesn't crash the whole scan."""
    mock_s3 = MagicMock()
    mock_s3.list_buckets.side_effect = Exception("S3 access denied")
    
    def client_side_effect(service, region_name=None):
        if service == 's3': return mock_s3
        return MagicMock()
    
    mock_boto_session.return_value.client.side_effect = client_side_effect
    
    scanner = ResourceScanner()
    results = await scanner.scan_all(regions=['us-east-1'])
    
    # Should complete without raising
    assert isinstance(results, list)
