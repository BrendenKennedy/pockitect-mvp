import atexit
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.core.config import WORKER_MAX

logger = logging.getLogger(__name__)

_executor: Optional[ThreadPoolExecutor] = None


def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=WORKER_MAX)
        logger.info("Task executor created with max_workers=%s", WORKER_MAX)

        @atexit.register
        def _shutdown_executor():
            try:
                _executor.shutdown(wait=False)
            except Exception:
                pass
    return _executor
