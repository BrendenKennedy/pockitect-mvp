"""
Tests for the AWS Quota Service.

These tests use mocking to avoid actual AWS API calls.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aws.quota import (
    QuotaService,
    QuotaCache,
    RegionInfo,
    InstanceTypeInfo,
    AMIInfo,
    KeyPairInfo,
    get_quota_service,
)


def test_quota_cache_initialization():
    """Test QuotaCache initializes with empty collections."""
    print("Testing QuotaCache initialization...")
    
    cache = QuotaCache()
    
    assert cache.regions == []
    assert cache.instance_types == {}
    assert cache.amis == {}
    assert cache.key_pairs == {}
    assert cache.vpcs == {}
    assert cache.last_updated is None
    assert cache.is_loading is False
    assert cache.error is None
    
    print("  ✓ QuotaCache initialization test passed")


def test_region_info():
    """Test RegionInfo dataclass."""
    print("Testing RegionInfo...")
    
    region = RegionInfo(
        region_id="us-east-1",
        region_name="US East (N. Virginia)",
        available=True
    )
    
    assert region.region_id == "us-east-1"
    assert region.region_name == "US East (N. Virginia)"
    assert region.available is True
    
    print("  ✓ RegionInfo test passed")


def test_instance_type_info():
    """Test InstanceTypeInfo dataclass and properties."""
    print("Testing InstanceTypeInfo...")
    
    instance = InstanceTypeInfo(
        instance_type="t3.micro",
        vcpus=2,
        memory_mb=1024,
        current_generation=True,
        free_tier_eligible=True,
        architecture="x86_64"
    )
    
    assert instance.instance_type == "t3.micro"
    assert instance.vcpus == 2
    assert instance.memory_mb == 1024
    assert instance.memory_gb == 1.0
    assert instance.current_generation is True
    assert instance.free_tier_eligible is True
    assert "t3.micro" in instance.display_name
    assert "2 vCPU" in instance.display_name
    assert "1.0 GB" in instance.display_name
    
    print("  ✓ InstanceTypeInfo test passed")


def test_ami_info():
    """Test AMIInfo dataclass."""
    print("Testing AMIInfo...")
    
    ami = AMIInfo(
        image_id="ami-12345678",
        name="Amazon Linux 2023",
        description="Latest Amazon Linux",
        architecture="x86_64",
        platform="linux",
        owner_alias="amazon",
        creation_date="2026-01-15T00:00:00Z"
    )
    
    assert ami.image_id == "ami-12345678"
    assert ami.name == "Amazon Linux 2023"
    assert ami.platform == "linux"
    
    print("  ✓ AMIInfo test passed")


def test_quota_service_initialization():
    """Test QuotaService initializes correctly."""
    print("Testing QuotaService initialization...")
    
    service = QuotaService()
    
    assert service.cache is not None
    assert service.is_ready is False
    assert service.needs_refresh is True
    
    print("  ✓ QuotaService initialization test passed")


def test_quota_service_needs_refresh():
    """Test needs_refresh logic."""
    print("Testing QuotaService needs_refresh...")
    
    service = QuotaService()
    
    # Should need refresh initially
    assert service.needs_refresh is True
    
    # After setting last_updated to now, should not need refresh
    service._cache.last_updated = datetime.now()
    assert service.needs_refresh is False
    
    # After 2 hours, should need refresh
    service._cache.last_updated = datetime.now() - timedelta(hours=2)
    assert service.needs_refresh is True
    
    print("  ✓ QuotaService needs_refresh test passed")


@patch('boto3.client')
def test_quota_service_fetch_regions(mock_boto_client):
    """Test fetching regions with mocked boto3."""
    print("Testing QuotaService region fetching...")
    
    # Mock EC2 client
    mock_ec2 = MagicMock()
    mock_ec2.describe_regions.return_value = {
        'Regions': [
            {'RegionName': 'us-east-1', 'OptInStatus': 'opt-in-not-required'},
            {'RegionName': 'us-west-2', 'OptInStatus': 'opt-in-not-required'},
            {'RegionName': 'eu-west-1', 'OptInStatus': 'opted-in'},
        ]
    }
    mock_boto_client.return_value = mock_ec2
    
    service = QuotaService()
    service._fetch_regions()
    
    assert len(service._cache.regions) == 3
    assert service._cache.regions[0].region_id == 'eu-west-1'  # Sorted
    assert service._cache.regions[1].region_id == 'us-east-1'
    assert service._cache.regions[2].region_id == 'us-west-2'
    
    print("  ✓ QuotaService region fetching test passed")


def test_get_quota_service_singleton():
    """Test that get_quota_service returns singleton."""
    print("Testing get_quota_service singleton...")
    
    # Reset the global
    import aws.quota as quota_module
    quota_module._quota_service = None
    
    service1 = get_quota_service()
    service2 = get_quota_service()
    
    assert service1 is service2
    
    print("  ✓ get_quota_service singleton test passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AWS Quota Service Tests")
    print("="*60 + "\n")
    
    test_quota_cache_initialization()
    test_region_info()
    test_instance_type_info()
    test_ami_info()
    test_quota_service_initialization()
    test_quota_service_needs_refresh()
    test_quota_service_fetch_regions()
    test_get_quota_service_singleton()
    
    print("\n" + "="*60)
    print("All quota service tests passed! ✓")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
