import json
from pathlib import Path

from app.core import listeners


class _FakeRedis:
    def __init__(self):
        self.status_events = []

    def publish_status(self, event_type, data=None, project_id=None, request_id=None, **extra_fields):
        payload = {"type": event_type, "data": data or {}, "request_id": request_id}
        payload.update(extra_fields)
        self.status_events.append(payload)


class _FakeScanner:
    def _scan_global_sync(self):
        return [
            {
                "id": "bucket-1",
                "type": "s3_bucket",
                "region": "global",
                "name": "bucket-1",
                "state": "active",
                "details": {},
                "tags": {},
            }
        ]

    def _scan_region_sync(self, region):
        return [
            {
                "id": f"i-{region}",
                "type": "ec2_instance",
                "region": region,
                "name": "test-instance",
                "state": "running",
                "details": {},
                "tags": {},
            }
        ]


def test_scan_writes_cache_and_publishes(tmp_path, monkeypatch):
    monkeypatch.setattr(listeners, "ResourceScanner", _FakeScanner)

    listener = listeners.CommandListener()
    listener.redis = _FakeRedis()
    listener._cache_dir = tmp_path

    listener._handle_scan_all({"regions": ["us-east-1"]}, request_id="req-1")

    global_path = tmp_path / "global.json"
    region_path = tmp_path / "us-east-1.json"

    assert global_path.exists()
    assert region_path.exists()

    global_data = json.loads(global_path.read_text(encoding="utf-8"))
    region_data = json.loads(region_path.read_text(encoding="utf-8"))

    assert global_data[0]["type"] == "s3_bucket"
    assert region_data[0]["region"] == "us-east-1"

    event_types = [e["type"] for e in listener.redis.status_events]
    assert "scan_chunk" in event_types
    assert "scan_complete" in event_types
