import pytest
import threading
import time
from app.core.redis_client import PubSubManager
from app.core.config import CHANNEL_RESOURCE_UPDATE

@pytest.mark.contract
def test_pubsub_manager_callback(redis_client_wrapper):
    """
    Verify PubSubManager thread correctly receives messages and invokes callback.
    """
    # Event to signal callback execution
    received = threading.Event()
    received_data = {}
    
    def callback(channel, data):
        received_data['channel'] = channel
        received_data['data'] = data
        received.set()
        
    # Start manager
    manager = PubSubManager([CHANNEL_RESOURCE_UPDATE], callback)
    manager.start()
    
    # Wait briefly for subscription to activate
    time.sleep(0.1)
    
    try:
        # Publish
        payload = {"msg": "update", "id": 1}
        redis_client_wrapper.publish(CHANNEL_RESOURCE_UPDATE, payload)
        
        # Wait for callback
        is_set = received.wait(timeout=2.0)
        assert is_set, "Callback was not invoked within timeout"
        
        assert received_data['channel'] == CHANNEL_RESOURCE_UPDATE
        assert received_data['data'] == payload
        
    finally:
        manager.stop()
        manager.join(timeout=1.0)
