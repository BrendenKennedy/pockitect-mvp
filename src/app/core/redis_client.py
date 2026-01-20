import json
import logging
import threading
import time
import redis
from typing import Callable, Dict, Any, Optional, Iterable, Set

from .config import REDIS_HOST, REDIS_PORT, REDIS_DB, CHANNEL_COMMANDS, CHANNEL_STATUS

logger = logging.getLogger(__name__)

class RedisClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RedisClient, cls).__new__(cls)
                cls._instance._init_connection()
            return cls._instance

    def _init_connection(self):
        try:
            self.client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True
            )
            self.client.ping()
            logger.info("Connected to Redis successfully.")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def get_connection(
        self, retries: int = 3, backoff_seconds: float = 0.5
    ) -> redis.Redis:
        if self.client is None:
            for attempt in range(retries):
                self._init_connection()
                if self.client is not None:
                    break
                time.sleep(backoff_seconds * (2 ** attempt))
        if self.client is None:
            raise redis.ConnectionError("Redis connection unavailable")
        return self.client

    def publish(self, channel: str, message: Any):
        """Publish a message to a channel. Message is JSON serialized automatically."""
        if not self.client:
            return
        
        if not isinstance(message, str):
            try:
                message = json.dumps(message)
            except (TypeError, ValueError):
                pass # Send as is if not serializable
        
        try:
            self.client.publish(channel, message)
        except Exception as e:
            logger.error(f"Error publishing to {channel}: {e}")

    def _build_event(self, event_type: str, data: Optional[Dict[str, Any]] = None,
                     project_id: Optional[str] = None, request_id: Optional[str] = None,
                     **extra_fields: Any) -> Dict[str, Any]:
        payload = {"type": event_type, "data": data or {}}
        if project_id:
            payload["project_id"] = project_id
        if request_id:
            payload["request_id"] = request_id
        payload.update(extra_fields)
        return payload

    def publish_command(self, event_type: str, data: Optional[Dict[str, Any]] = None,
                        project_id: Optional[str] = None, request_id: Optional[str] = None,
                        **extra_fields: Any):
        """Publish a command intent to the command channel."""
        payload = self._build_event(event_type, data, project_id, request_id, **extra_fields)
        self.publish(CHANNEL_COMMANDS, payload)

    def publish_status(self, event_type: str, data: Optional[Dict[str, Any]] = None,
                       project_id: Optional[str] = None, request_id: Optional[str] = None,
                       **extra_fields: Any):
        """Publish a status update to the status channel."""
        payload = self._build_event(event_type, data, project_id, request_id, **extra_fields)
        self.publish(CHANNEL_STATUS, payload)

    def parse_pubsub_message(self, message: Any) -> Optional[Dict[str, Any]]:
        """Safely parse a pubsub message into a dict payload."""
        if not isinstance(message, dict):
            return None
        raw = message.get("data")
        if raw is None:
            return None
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def iter_events(
        self,
        channel: str,
        request_id: Optional[str] = None,
        allowed_types: Optional[Set[str]] = None,
        timeout: float = 0.5,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Iterate parsed pub/sub events with optional filtering and stop callback."""
        if not self.client:
            return
        pubsub = self.client.pubsub()
        pubsub.subscribe(channel)
        try:
            while True:
                if stop_check and stop_check():
                    break
                msg = pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=timeout
                )
                if not msg:
                    continue
                data = self.parse_pubsub_message(msg)
                if not data:
                    continue
                if request_id is not None and data.get("request_id") and data.get("request_id") != request_id:
                    continue
                if allowed_types and data.get("type") not in allowed_types:
                    continue
                yield data
        finally:
            pubsub.close()

    def hset_json(self, name: str, key: str, value: Any):
        """Set a hash field to a JSON serialized value."""
        if not self.client:
            return
        try:
            self.client.hset(name, key, json.dumps(value))
        except Exception as e:
            logger.error(f"Error setting hash {name} key {key}: {e}")

    def hget_all_json(self, name: str) -> Dict[str, Any]:
        """Get all fields from a hash and deserialize JSON values."""
        if not self.client:
            return {}
        try:
            data = self.client.hgetall(name)
            return {k: json.loads(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error getting hash {name}: {e}")
            return {}

class PubSubManager(threading.Thread):
    """
    Manages a background thread for Redis Pub/Sub subscription.
    Callbacks are invoked when messages arrive.
    """
    def __init__(self, channels: list[str], callback: Callable[[str, Any], None]):
        super().__init__()
        try:
            self.redis = RedisClient().get_connection()
        except redis.ConnectionError as exc:
            logger.error("Cannot start PubSubManager: %s", exc)
            self.redis = None
        self.channels = channels
        self.callback = callback
        self.pubsub = None
        self._stop_event = threading.Event()
        self.daemon = True

    def run(self):
        if not self.redis:
            logger.error("Cannot start PubSubManager: No Redis connection.")
            return

        self.pubsub = self.redis.pubsub()
        for channel in self.channels:
            self.pubsub.subscribe(channel)
        
        logger.info(f"Subscribed to channels: {self.channels}")

        while not self._stop_event.is_set():
            try:
                message = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    channel = message["channel"]
                    payload = RedisClient().parse_pubsub_message(message)
                    if payload is None:
                        payload = message.get("data")
                    self.callback(channel, payload)
            except Exception as e:
                logger.error(f"PubSub error: {e}")
                if self._stop_event.is_set():
                    break
                # Simple backoff could be added here

    def stop(self):
        self._stop_event.set()
        if self.pubsub:
            self.pubsub.close()
