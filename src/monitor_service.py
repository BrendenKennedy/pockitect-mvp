import json
import logging
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal

# Import ScannedResource from the original location to match MonitorTab's expectation
from app.core.aws.scanner import ScannedResource, ALL_REGIONS

# New imports
from app.core.redis_client import RedisClient
from app.core.config import WORKSPACE_ROOT
from storage import load_project_regions_cache, get_project_regions

logger = logging.getLogger(__name__)

@dataclass
class ScanRequest:
    regions: Optional[List[str]] = None
    request_id: Optional[str] = None

class ResourceMonitoringService(QThread):
    """
    Background service that manages AWS resource scanning via Redis pub/sub.
    """
    scan_completed = Signal(list)  # Emits List[ScannedResource]
    scan_progress = Signal(str)
    scan_error = Signal(str)
    status_event = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_requested = False
        self.redis = RedisClient()
        self._active_scan_id = None
        self._scan_cache_dir = WORKSPACE_ROOT / "data" / "cache"
        self._resources_by_key: Dict[str, ScannedResource] = {}

    def request_scan(self, regions: Optional[List[str]] = None, request_id: str = None):
        """Trigger a background scan via Redis command."""
        try:
            self._active_scan_id = request_id or uuid.uuid4().hex
            if regions is None:
                # Try to load from cache first
                regions = load_project_regions_cache()
                # If cache is empty, get regions from actual projects
                if not regions:
                    regions = get_project_regions()
                # If still no regions found, fall back to all AWS regions
                if not regions:
                    regions = ALL_REGIONS
            self.redis.publish_command("scan_all_regions", {"regions": regions}, request_id=self._active_scan_id)
            self.scan_progress.emit("Scan request queued...")
        except Exception as e:
            self.scan_error.emit(f"Failed to queue scan: {e}")

    def stop(self):
        """Stop the service."""
        self._stop_requested = True
        self.wait()

    def run(self):
        self.scan_progress.emit("Monitoring service ready...")
        self._load_cached_resources()

        while not self._stop_requested:
            self.msleep(500)

    def handle_status_event(self, data: Dict):
        if not isinstance(data, dict):
            return
        if self._active_scan_id and data.get("request_id") and data.get("request_id") != self._active_scan_id:
            return

        event_type = data.get("type")
        self.status_event.emit(data)

        if event_type == "scan_chunk":
            self._handle_scan_chunk(data)
        elif event_type == "scan_complete":
            self._handle_scan_complete(data)

    def _handle_scan_chunk(self, data: Dict):
        payload = data.get("data") or {}
        file_path = payload.get("file")
        region = payload.get("region", "unknown")
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)
            # Clear old resources for this region before merging
            for key in list(self._resources_by_key.keys()):
                if key.startswith(f"{region}:"):
                    self._resources_by_key.pop(key, None)

            for item in raw_items:
                res_region = item.get("region") or region
                res_type = item.get("type")
                res_id = item.get("id")
                if not res_region or not res_type or not res_id:
                    continue
                res = ScannedResource(
                    id=res_id,
                    type=res_type,
                    region=res_region,
                    name=item.get("name"),
                    state=item.get("state"),
                    tags=item.get("tags", {}),
                    details=item.get("details", {}),
                )
                key = f"{res.region}:{res.type}:{res.id}"
                self._resources_by_key[key] = res
            resources = list(self._resources_by_key.values())
            self.scan_completed.emit(resources)
            self.scan_progress.emit(f"Loaded scan chunk: {region} ({len(raw_items)} resources)")
        except Exception as e:
            logger.error("Failed reading scan chunk: %s", e)
            self.scan_error.emit(f"Scan chunk failed for {region}: {e}")

    def _handle_scan_complete(self, data: Dict):
        return

    def _load_cached_resources(self):
        if not self._scan_cache_dir.exists():
            return
        for file_path in self._scan_cache_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_items = json.load(f)
                for item in raw_items:
                    res = ScannedResource(
                        id=item.get("id"),
                        type=item.get("type"),
                        region=item.get("region"),
                        name=item.get("name"),
                        state=item.get("state"),
                        tags=item.get("tags", {}),
                        details=item.get("details", {}),
                    )
                    if res.id and res.type and res.region:
                        key = f"{res.region}:{res.type}:{res.id}"
                        self._resources_by_key[key] = res
            except Exception:
                continue
        if self._resources_by_key:
            self.scan_completed.emit(list(self._resources_by_key.values()))
