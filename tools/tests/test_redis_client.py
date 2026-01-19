import pytest
import json
import threading
import time
from app.core.redis_client import RedisClient

@pytest.mark.unit
def test_redis_connection_singleton(redis_client_wrapper):
    """Verify that RedisClient is a singleton."""
    c1 = RedisClient()
    c2 = RedisClient()
    assert c1 is c2
    assert c1.client is not None

@pytest.mark.unit
def test_publish(redis_client_wrapper, fake_redis):
    """Verify publishing sends message to Redis."""
    pubsub = fake_redis.pubsub()
    pubsub.subscribe("test_channel")
    
    # Wait for subscription to register
    time.sleep(0.01)
    
    redis_client_wrapper.publish("test_channel", {"hello": "world"})
    
    # Consume messages until we find ours or timeout
    found = False
    start = time.time()
    while time.time() - start < 1.0:
        msg = pubsub.get_message(ignore_subscribe_messages=True)
        if msg:
            assert msg['channel'] == "test_channel"
            assert json.loads(msg['data']) == {"hello": "world"}
            found = True
            break
        time.sleep(0.01)
        
    assert found, "Message not received on channel"

@pytest.mark.unit
def test_hset_hget_json(redis_client_wrapper):
    """Verify JSON serialization for hash operations."""
    data = {"id": 123, "name": "test"}
    redis_client_wrapper.hset_json("myhash", "key1", data)
    
    result = redis_client_wrapper.hget_all_json("myhash")
    assert result["key1"] == data
    
@pytest.mark.unit
def test_reconnect_logic(redis_client_wrapper):
    """Verify get_connection tries to reconnect if client is None."""
    # Simulate disconnection
    redis_client_wrapper.client = None
    
    conn = redis_client_wrapper.get_connection()
    assert conn is not None
    assert redis_client_wrapper.client is not None
