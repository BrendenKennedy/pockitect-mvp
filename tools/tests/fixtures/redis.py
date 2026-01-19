import pytest
import fakeredis
from unittest.mock import patch
from app.core.redis_client import RedisClient

@pytest.fixture
def fake_redis_server():
    return fakeredis.FakeServer()

@pytest.fixture
def fake_redis(fake_redis_server):
    # decode_responses=True is important for our app
    return fakeredis.FakeRedis(server=fake_redis_server, decode_responses=True)

@pytest.fixture(autouse=True)
def patch_redis_client(fake_redis):
    # Reset singleton before test
    RedisClient._instance = None
    
    # Patch redis.Redis to return our fake instance
    # This ensures that when RedisClient() calls redis.Redis(), it gets our fake object
    with patch('redis.Redis', return_value=fake_redis):
        yield
        
    # Reset singleton after test
    RedisClient._instance = None
    fake_redis.flushall()

@pytest.fixture
def redis_client_wrapper(patch_redis_client):
    """Return the application's RedisClient wrapper."""
    return RedisClient()
