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
        return self.redis.iter_events(
            CHANNEL_STATUS,
            request_id=request_id,
            allowed_types=allowed_types,
            timeout=timeout,
            stop_check=self.isInterruptionRequested,
        )
