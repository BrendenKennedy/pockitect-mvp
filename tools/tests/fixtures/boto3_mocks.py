import pytest
from unittest.mock import MagicMock, patch
import botocore.session

@pytest.fixture
def mock_boto_session():
    """Patches boto3.Session globally."""
    with patch('boto3.Session') as mock:
        yield mock

@pytest.fixture
def mock_s3_client(mock_boto_session):
    client = MagicMock()
    # Setup default behaviors
    client.list_buckets.return_value = {'Buckets': []}
    
    def side_effect(service_name, region_name=None):
        if service_name == 's3':
            return client
        return MagicMock()
        
    mock_boto_session.return_value.client.side_effect = side_effect
    return client
