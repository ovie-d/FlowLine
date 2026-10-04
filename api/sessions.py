"""In-memory agent chat sessions. History stays on the server."""

from __future__ import annotations

from typing import Any

SESSIONS: dict[str, list[dict[str, Any]]] = {}


def get_history(session_id: str) -> list[dict[str, Any]]:
    return list(SESSIONS.get(session_id, []))


def set_history(session_id: str, history: list[dict[str, Any]]) -> None:
    SESSIONS[session_id] = list(history)


def reset_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)


def clear_all() -> None:
    """Test helper."""
    SESSIONS.clear()
