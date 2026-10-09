"""Public online demo: per-visitor sandbox and a small, hard-capped AI budget.

Active only when FLOWLINE_DEMO=1 (the hosted website). Local installs are unaffected.

- Visitor: a random id the browser keeps (header X-Flowline-Visitor) plus the client IP
  (hashed, never stored raw). Set per request by api.main's middleware.
- Sandbox: decisions and crew-table edits are stored per visitor and expire after
  SANDBOX_HOURS, so every visitor (and every presenter) starts from the clean demo data.
- AI quota: AI_PROMPTS_PER_VISITOR prompts per visitor per UTC day (also capped per IP),
  and a hard total of AI_DAILY_BUDGET_USD across everyone, from the usage log.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from contextvars import ContextVar
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg

SANDBOX_HOURS = 24
DEFAULT_PROMPTS_PER_VISITOR = 3
DEFAULT_PROMPTS_PER_IP = 10  # shared networks (campus, office) get some headroom
DEFAULT_DAILY_BUDGET_USD = 1.0

DEMO_NOTE = (
    "This is a free online demo. We'd like everyone interested to be able to try it, "
    "but we're students on a small budget, so each visitor gets {limit} AI prompts per "
    "day."
)

_VISITOR_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_SALT = os.environ.get("AI_IP_SALT") or secrets.token_hex(16)

_visitor: ContextVar[str] = ContextVar("flowline_visitor", default="")
_ip_hash: ContextVar[str] = ContextVar("flowline_ip_hash", default="")


class QuotaExceeded(Exception):
    """The visitor (or the whole demo) has used today's AI allowance."""


def enabled() -> bool:
    return os.environ.get("FLOWLINE_DEMO", "").strip().lower() in {"1", "true", "yes"}


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, default)))
    except ValueError:
        return default


def prompts_per_visitor() -> int:
    return _int_env("AI_PROMPTS_PER_VISITOR", DEFAULT_PROMPTS_PER_VISITOR)


def prompts_per_ip() -> int:
    return _int_env("AI_PROMPTS_PER_IP", DEFAULT_PROMPTS_PER_IP)


def daily_budget_usd() -> float:
    return _float_env("AI_DAILY_BUDGET_USD", DEFAULT_DAILY_BUDGET_USD)


# ------------------------------------------------------------------ visitor context
def clean_visitor_id(raw: str | None) -> str:
    raw = (raw or "").strip()
    return raw if _VISITOR_RE.match(raw) else ""


def hash_ip(ip: str | None) -> str:
    return hashlib.sha256(f"{_SALT}:{ip or ''}".encode()).hexdigest()[:20] if ip else ""


def bind(visitor_id: str, ip: str | None) -> tuple[Any, Any]:
    """Set the current visitor for this request; returns tokens for reset()."""
    return _visitor.set(clean_visitor_id(visitor_id)), _ip_hash.set(hash_ip(ip))


def reset(tokens: tuple[Any, Any]) -> None:
    _visitor.reset(tokens[0])
    _ip_hash.reset(tokens[1])


def visitor() -> str:
    """Sandbox key: the visitor id in demo mode, '' (shared data) otherwise."""
    return _visitor.get() if enabled() else ""


def raw_visitor() -> str:
    return _visitor.get()


# ------------------------------------------------------------------ AI quota
SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_quota (
  day    date NOT NULL,
  key    text NOT NULL,
  count  integer NOT NULL DEFAULT 0,
  PRIMARY KEY (day, key)
);
"""


def _today() -> date:
    return datetime.now(UTC).date()


def spent_today_usd(log_path: Path | None = None) -> float:
    """Estimated AI spend today (UTC) from the usage log."""
    from core.agent.budget import USAGE_LOG

    path = log_path or USAGE_LOG
    if not path.exists():
        return 0.0
    day = _today().isoformat()
    total = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(e.get("ts", "")).startswith(day):
            total += float(e.get("cost_usd") or 0.0)
    return round(total, 4)


def _counts(conn: psycopg.Connection) -> tuple[int, int]:
    conn.execute(SCHEMA)
    rows = {
        r["key"]: r["count"]
        for r in conn.execute(
            "SELECT key, count FROM ai_quota WHERE day = %s AND key = ANY(%s)",
            (_today(), [f"v:{_visitor.get()}", f"ip:{_ip_hash.get()}"]),
        )
    }
    return rows.get(f"v:{_visitor.get()}", 0), rows.get(f"ip:{_ip_hash.get()}", 0)


def quota_status(conn: psycopg.Connection | None) -> dict[str, Any]:
    """What the app shows: limit, prompts left today, and whether the day's budget is used."""
    limit = prompts_per_visitor()
    remaining = limit
    if conn is not None and _visitor.get():
        used_v, used_ip = _counts(conn)
        # The tighter of the two allowances (visitor, shared IP) is what is left.
        remaining = max(0, min(limit - used_v, prompts_per_ip() - used_ip))
    budget_left = spent_today_usd() < daily_budget_usd()
    return {
        "demo": True,
        "limit": limit,
        "remaining": remaining if budget_left else 0,
        "daily_budget_reached": not budget_left,
        "note": DEMO_NOTE.format(limit=limit),
    }


def consume_prompt(conn: psycopg.Connection) -> dict[str, Any]:
    """Count one AI prompt for this visitor, or raise QuotaExceeded with a plain reason."""
    if not _visitor.get():
        raise QuotaExceeded("Reload the page to start a demo session, then try again.")
    if spent_today_usd() >= daily_budget_usd():
        raise QuotaExceeded(
            "Today's AI budget for the online demo is used up. Please try again tomorrow, "
            "or install Flowline to use your own key. Everything else works."
        )
    used_v, used_ip = _counts(conn)
    limit = prompts_per_visitor()
    if used_v >= limit or used_ip >= prompts_per_ip():
        raise QuotaExceeded(
            f"You've used your {limit} AI prompts for today. Thanks for trying Flowline! "
            "They reset at midnight UTC. Everything else in the demo keeps working."
        )
    with conn.transaction():
        for key in (f"v:{_visitor.get()}", f"ip:{_ip_hash.get()}"):
            conn.execute(
                "INSERT INTO ai_quota (day, key, count) VALUES (%s, %s, 1) "
                "ON CONFLICT (day, key) DO UPDATE SET count = ai_quota.count + 1",
                (_today(), key),
            )
    return quota_status(conn)


def refund_prompt(conn: psycopg.Connection) -> None:
    """Give the prompt back when the AI call failed before answering."""
    with conn.transaction():
        for key in (f"v:{_visitor.get()}", f"ip:{_ip_hash.get()}"):
            conn.execute(
                "UPDATE ai_quota SET count = GREATEST(count - 1, 0) WHERE day = %s AND key = %s",
                (_today(), key),
            )
