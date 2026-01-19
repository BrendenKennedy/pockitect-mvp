import pytest
import boto3
from unittest.mock import patch, MagicMock
from app.core.aws.credentials_helper import get_session

@pytest.mark.unit
def test_get_session_with_keyring():
    """Verify session is created with keyring credentials if available."""
    with patch('keyring.get_password') as mock_get_pass:
        # Mock keyring returning values
        def side_effect(service, user):
            if user == "aws_access_key_id": return "AKIA_KEYRING"
            if user == "aws_secret_access_key": return "SECRET_KEYRING"
            return None
        mock_get_pass.side_effect = side_effect
        
        session = get_session(region_name="us-west-2")
        
        # Verify credentials were passed to session
        creds = session.get_credentials()
        assert creds.access_key == "AKIA_KEYRING"
        assert creds.secret_key == "SECRET_KEYRING"
        assert session.region_name == "us-west-2"

@pytest.mark.unit
def test_get_session_fallback():
    """Verify fallback to default session if keyring is empty/fails."""
    with patch('keyring.get_password', return_value=None):
        # We can't easily mock the default environment without messing up other tests,
        # but we can verify it returns a session.
        session = get_session(region_name="eu-central-1")
        assert isinstance(session, boto3.Session)
        assert session.region_name == "eu-central-1"
