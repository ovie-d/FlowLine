"""Append-only inspection decision log (repo-root JSON)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_ACTIONS = frozenset({"inspect", "escalate", "defer"})
VALID_SOURCES = frozenset({"planner", "agent_triage"})

DECISIONS_PATH = Path(__file__).resolve().parent.parent / "inspection_decisions.json"

_decisions_path_override: Path | None = None


def set_decisions_path(path: Path | None) -> None:
    """Test helper: redirect the decisions file (None restores default)."""
    global _decisions_path_override
    _decisions_path_override = path


def decisions_path() -> Path:
    return _decisions_path_override or DECISIONS_PATH


def read_decisions() -> list[dict[str, Any]]:
    """Return logged decisions (empty list if missing/corrupt)."""
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


def append_decision(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate and append one decision. Raises ValueError on bad action/source."""
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

    policy = entry.get("policy")
    if policy is None:
        policy = {}
    if not isinstance(policy, dict):
        raise TypeError("policy must be a dict")

    stored = {
        "id": str(entry.get("id") or uuid.uuid4()),
        "ts": entry.get("ts") or datetime.now(timezone.utc).isoformat(),
        "corridor": str(entry["corridor"]),
        "action": action,
        "priority": str(entry["priority"]),
        "reason": str(entry["reason"]),
        "policy": dict(policy),
        "source": source,
    }

    existing = read_decisions()
    existing.append(stored)
    path = decisions_path()
    path.write_text(json.dumps(existing, indent=2))
    return stored
