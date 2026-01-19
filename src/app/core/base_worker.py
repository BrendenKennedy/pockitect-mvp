from typing import Dict, Iterable, Optional, Set

from PySide6.QtCore import QThread

from app.core.config import CHANNEL_STATUS
from app.core.redis_client import RedisClient


class BaseCommandWorker(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.redis = RedisClient()

    def iter_status_events(
        self,
        request_id: str,
        allowed_types: Optional[Set[str]] = None,
        timeout: float = 0.5,
    ) -> Iterable[Dict]:
        pubsub = self.redis.client.pubsub()
        pubsub.subscribe(CHANNEL_STATUS)
        try:
            while True:
                if self.isInterruptionRequested():
                    break
                msg = pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=timeout
                )
                if not msg:
                    continue
                data = self.redis.parse_pubsub_message(msg)
                if not data:
                    continue
                if data.get("request_id") and data.get("request_id") != request_id:
                    continue
                if allowed_types and data.get("type") not in allowed_types:
                    continue
                yield data
        finally:
            pubsub.close()
