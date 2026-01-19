import logging
import boto3
import keyring
from botocore.exceptions import NoCredentialsError

from app.core.config import (
    KEYRING_SERVICE,
    KEYRING_USER_ACCESS_KEY,
    KEYRING_USER_SECRET_KEY,
)

logger = logging.getLogger(__name__)

def get_session(
    region_name: str = None,
    access_key: str = None,
    secret_key: str = None,
) -> boto3.Session:
    """
    Create a boto3 session with credentials from keyring if available,
    falling back to default chain (env vars, ~/.aws/credentials).
    """
    if access_key and secret_key:
        return boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
        )

    try:
        stored_access_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_ACCESS_KEY)
        stored_secret_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER_SECRET_KEY)

        if stored_access_key and stored_secret_key:
            return boto3.Session(
                aws_access_key_id=stored_access_key,
                aws_secret_access_key=stored_secret_key,
                region_name=region_name,
            )
    except Exception as e:
        logger.warning(f"Failed to retrieve credentials from keyring: {e}")
        
    # Fallback to default
    return boto3.Session(region_name=region_name)
