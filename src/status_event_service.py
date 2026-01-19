import json
import logging
from PySide6.QtCore import QThread, Signal

from app.core.redis_client import RedisClient
from app.core.config import CHANNEL_STATUS

logger = logging.getLogger(__name__)


class StatusEventService(QThread):
    """
    Background service that forwards all Redis status events to the UI.
    """

    status_event = Signal(dict)
    scan_event = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_requested = False
        self.redis = RedisClient()
        self.pubsub = None

    def stop(self):
        self._stop_requested = True
        if self.pubsub:
            self.pubsub.close()
        self.wait()

    def run(self):
        if not self.redis.client:
            logger.error("StatusEventService: Redis not connected")
            return

        self.pubsub = self.redis.client.pubsub()
        self.pubsub.subscribe(CHANNEL_STATUS)

        while not self._stop_requested:
            try:
                msg = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    data = json.loads(msg["data"])
                    if isinstance(data, dict):
                        self.status_event.emit(data)
                        if data.get("type") in ("scan_chunk", "scan_complete"):
                            self.scan_event.emit(data)
            except Exception as exc:
                logger.error("StatusEventService error: %s", exc)
                self.msleep(500)
