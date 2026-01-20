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

    def stop(self):
        self._stop_requested = True
        self.wait()

    def run(self):
        if not self.redis.client:
            logger.error("StatusEventService: Redis not connected")
            return

        try:
            for data in self.redis.iter_events(
                CHANNEL_STATUS,
                timeout=1.0,
                stop_check=lambda: self._stop_requested,
            ):
                self.status_event.emit(data)
                if data.get("type") in ("scan_chunk", "scan_complete"):
                    self.scan_event.emit(data)
        except Exception as exc:
            logger.error("StatusEventService error: %s", exc)
            self.msleep(500)
