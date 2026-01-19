from app.core.listeners import CommandListener


class _FakeRedis:
    def __init__(self):
        self.status_events = []

    def publish_status(self, event_type, data=None, project_id=None, request_id=None, **extra_fields):
        payload = {"type": event_type, "data": data or {}, "request_id": request_id}
        payload.update(extra_fields)
        self.status_events.append(payload)


class _FakeEC2:
    def __init__(self):
        self.started = []
        self.stopped = []

    def start_instances(self, InstanceIds):
        self.started.extend(InstanceIds)

    def stop_instances(self, InstanceIds):
        self.stopped.extend(InstanceIds)


class _FakeRDS:
    def __init__(self):
        self.started = []
        self.stopped = []

    def start_db_instance(self, DBInstanceIdentifier):
        self.started.append(DBInstanceIdentifier)

    def stop_db_instance(self, DBInstanceIdentifier):
        self.stopped.append(DBInstanceIdentifier)


class _FakeSession:
    def __init__(self, ec2, rds):
        self._ec2 = ec2
        self._rds = rds

    def client(self, service, region_name=None):
        if service == "ec2":
            return self._ec2
        if service == "rds":
            return self._rds
        raise ValueError(service)


def test_power_handler(monkeypatch):
    listener = CommandListener()
    listener.redis = _FakeRedis()

    fake_ec2 = _FakeEC2()
    fake_rds = _FakeRDS()
    monkeypatch.setattr(
        "app.core.listeners.get_session",
        lambda region_name=None: _FakeSession(fake_ec2, fake_rds),
    )

    listener._handle_power(
        {
            "action": "start",
            "resources": [
                {"id": "i-123", "type": "ec2_instance", "region": "us-east-1"},
                {"id": "db-123", "type": "rds_instance", "region": "us-east-1"},
            ],
        },
        request_id="req-1",
    )

    assert fake_ec2.started == ["i-123"]
    assert fake_rds.started == ["db-123"]
    assert any(event.get("status") == "success" for event in listener.redis.status_events)
