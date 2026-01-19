"""Session management for AI multi-turn conversations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.redis_client import RedisClient


class SessionManager:
    REDIS_KEY_PREFIX = "ai:session:"
    MAX_HISTORY = 5
    TTL_SECONDS = 3600
    MAX_HISTORY_CHARS = 16000  # ~4k tokens estimate

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        max_history: int = MAX_HISTORY,
        ttl_seconds: int = TTL_SECONDS,
    ) -> None:
        self._redis = redis_client or RedisClient()
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{self.REDIS_KEY_PREFIX}{session_id}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if not session_id:
            return {"turns": [], "created_at": self._now(), "last_blueprint": None}
        try:
            conn = self._redis.get_connection()
            payload = conn.get(self._key(session_id))
            if not payload:
                return {"turns": [], "created_at": self._now(), "last_blueprint": None}
            return json_loads(payload)
        except Exception:
            return {"turns": [], "created_at": self._now(), "last_blueprint": None}

    def append_turn(
        self,
        session_id: str,
        user: str,
        assistant: str,
        blueprint: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not session_id:
            return

        session = self.get_session(session_id)
        turns: List[Dict[str, Any]] = session.get("turns", [])
        turns.append({"user": user, "assistant": assistant, "blueprint": blueprint})
        turns = turns[-self.max_history :]

        session["turns"] = turns
        session["last_blueprint"] = blueprint or session.get("last_blueprint")
        session["updated_at"] = self._now()

        try:
            conn = self._redis.get_connection()
            conn.setex(self._key(session_id), self.ttl_seconds, json_dumps(session))
        except Exception:
            return

    def get_history_for_prompt(self, session_id: str) -> str:
        session = self.get_session(session_id)
        turns = session.get("turns", [])
        if not turns:
            return ""

        lines: List[str] = []
        for idx, turn in enumerate(turns, start=1):
            user = (turn.get("user") or "").strip()
            assistant = (turn.get("assistant") or "").strip()
            if user:
                lines.append(f"Turn {idx} User: {self._truncate(user)}")
            if assistant:
                lines.append(f"Turn {idx} Assistant: {self._truncate(assistant)}")

        history = "\n".join(lines).strip()
        if len(history) > self.MAX_HISTORY_CHARS:
            lines = lines[-4:]
            history = "Earlier turns summarized.\n" + "\n".join(lines)
        return history

    def get_last_blueprint(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        return session.get("last_blueprint")

    def clear_session(self, session_id: str) -> None:
        if not session_id:
            return
        try:
            conn = self._redis.get_connection()
            conn.delete(self._key(session_id))
        except Exception:
            return

    def _truncate(self, text: str, max_len: int = 400) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."


def json_dumps(payload: Dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


def json_loads(payload: str) -> Dict[str, Any]:
    import json

    return json.loads(payload)
