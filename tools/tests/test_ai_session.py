from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.session_manager import SessionManager


class FakeConn:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)


class FakeRedisClient:
    def __init__(self):
        self.conn = FakeConn()

    def get_connection(self):
        return self.conn


def test_session_append_and_limit():
    manager = SessionManager(redis_client=FakeRedisClient(), max_history=2, ttl_seconds=60)
    session_id = "test-session"

    manager.append_turn(session_id, "first", "ok", blueprint={"project": {"name": "one"}})
    manager.append_turn(session_id, "second", "ok", blueprint={"project": {"name": "two"}})
    manager.append_turn(session_id, "third", "ok", blueprint={"project": {"name": "three"}})

    session = manager.get_session(session_id)
    assert len(session["turns"]) == 2
    assert session["turns"][0]["user"] == "second"
    assert session["turns"][1]["user"] == "third"


def test_history_formatting():
    manager = SessionManager(redis_client=FakeRedisClient(), max_history=5, ttl_seconds=60)
    session_id = "history-session"

    manager.append_turn(session_id, "Create a blog", "Generated blueprint", blueprint=None)
    history = manager.get_history_for_prompt(session_id)

    assert "Turn 1 User" in history
    assert "Create a blog" in history


def test_clear_session():
    manager = SessionManager(redis_client=FakeRedisClient(), max_history=5, ttl_seconds=60)
    session_id = "clear-session"

    manager.append_turn(session_id, "test", "ok", blueprint=None)
    manager.clear_session(session_id)
    session = manager.get_session(session_id)

    assert session["turns"] == []
