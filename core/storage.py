"""Append-only inspection decision log (JSON by default; SQLite or Postgres optional).

DECISIONS_BACKEND = json | sqlite | postgres (postgres uses DATABASE_URL).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import demo
from core.db import connect, db_path, init_schema
from core.pg import connect as pg_connect

VALID_ACTIONS = frozenset({"inspect", "escalate", "defer"})
VALID_SOURCES = frozenset({"planner", "agent_triage"})
VALID_PRIORITIES = frozenset({"P1", "P2", "P3"})

DECISIONS_PATH = Path(__file__).resolve().parent.parent / "inspection_decisions.json"

_decisions_path_override: Path | None = None


def set_decisions_path(path: Path | None) -> None:
    """Test helper: redirect the decisions file (None restores default)."""
    global _decisions_path_override
    _decisions_path_override = path


def decisions_path() -> Path:
    return _decisions_path_override or DECISIONS_PATH


def _backend() -> str:
    return os.environ.get("DECISIONS_BACKEND", "json").strip().lower()


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    action = str(entry.get("action", "")).strip().lower()
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"action must be one of {sorted(VALID_ACTIONS)}, got {action!r}"
        )

    source = str(entry.get("source", "planner")).strip()
    if source not in VALID_SOURCES:
        raise ValueError(
            f"source must be one of {sorted(VALID_SOURCES)}, got {source!r}"
        )

    priority = str(entry["priority"]).strip()
    if _backend() in {"sqlite", "postgres"} and priority not in VALID_PRIORITIES:
        raise ValueError(
            f"priority must be one of {sorted(VALID_PRIORITIES)}, got {priority!r}"
        )

    policy = entry.get("policy")
    if policy is None:
        policy = {}
    if not isinstance(policy, dict):
        raise TypeError("policy must be a dict")

    return {
        "id": str(entry.get("id") or uuid.uuid4()),
        "ts": entry.get("ts") or datetime.now(timezone.utc).isoformat(),
        "corridor": str(entry["corridor"]),
        "action": action,
        "priority": priority,
        "reason": str(entry["reason"]),
        "policy": dict(policy),
        "source": source,
    }


def _read_decisions_json() -> list[dict[str, Any]]:
    path = decisions_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [dict(row) for row in data if isinstance(row, dict)]


def _append_decision_json(stored: dict[str, Any]) -> dict[str, Any]:
    existing = _read_decisions_json()
    existing.append(stored)
    path = decisions_path()
    path.write_text(json.dumps(existing, indent=2))
    return stored


def _read_decisions_sqlite() -> list[dict[str, Any]]:
    path = db_path()
    if not path.exists():
        return []
    with connect(path) as conn:
        init_schema(conn)
        rows = conn.execute(
            "SELECT id, ts, corridor, action, priority, reason, policy_json, source "
            "FROM decisions ORDER BY ts, id"
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        policy_raw = row["policy_json"]
        try:
            policy = json.loads(policy_raw) if policy_raw else {}
        except json.JSONDecodeError:
            policy = {}
        if not isinstance(policy, dict):
            policy = {}
        out.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "corridor": row["corridor"],
                "action": row["action"],
                "priority": row["priority"],
                "reason": row["reason"],
                "policy": policy,
                "source": row["source"],
            }
        )
    return out


def _append_decision_sqlite(stored: dict[str, Any]) -> dict[str, Any]:
    with connect(db_path()) as conn:
        init_schema(conn)
        conn.execute(
            "INSERT INTO decisions "
            "(id, ts, corridor, action, priority, reason, policy_json, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stored["id"],
                stored["ts"],
                stored["corridor"],
                stored["action"],
                stored["priority"],
                stored["reason"],
                json.dumps(stored["policy"]),
                stored["source"],
            ),
        )
        conn.commit()
    return stored


def _read_decisions_pg() -> list[dict[str, Any]]:
    # Online demo: each visitor sees only their own decisions (last 24 h); locally the
    # visitor is '' and this is the shared log.
    with pg_connect() as conn:
        rows = conn.execute(
            "SELECT id, ts, corridor, action, priority, reason, policy, source "
            "FROM decision_log WHERE visitor_id = %s "
            "AND (visitor_id = '' OR ts > now() - make_interval(hours => %s)) "
            "ORDER BY ts, id",
            (demo.visitor(), demo.SANDBOX_HOURS),
        ).fetchall()
    return [
        {**row, "ts": row["ts"].isoformat(), "policy": dict(row["policy"] or {})}
        for row in rows
    ]


def _append_decision_pg(stored: dict[str, Any]) -> dict[str, Any]:
    with pg_connect() as conn:
        conn.execute(
            "INSERT INTO decision_log "
            "(id, ts, corridor, action, priority, reason, policy, source, visitor_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)",
            (
                stored["id"],
                stored["ts"],
                stored["corridor"],
                stored["action"],
                stored["priority"],
                stored["reason"],
                json.dumps(stored["policy"]),
                stored["source"],
                demo.visitor(),
            ),
        )
    return stored


def read_decisions() -> list[dict[str, Any]]:
    """Return logged decisions (empty list if missing/corrupt)."""
    if _backend() == "postgres":
        return _read_decisions_pg()
    if _backend() == "sqlite":
        try:
            return _read_decisions_sqlite()
        except Exception:  # noqa: BLE001 — fall back to JSON on any SQLite error
            return _read_decisions_json()
    return _read_decisions_json()


def append_decision(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate and append one decision. Raises ValueError on bad action/source."""
    stored = _normalize_entry(entry)
    if _backend() == "postgres":
        return _append_decision_pg(stored)
    if _backend() == "sqlite":
        try:
            return _append_decision_sqlite(stored)
        except Exception:  # noqa: BLE001 — fall back to JSON on any SQLite error
            return _append_decision_json(stored)
    return _append_decision_json(stored)
