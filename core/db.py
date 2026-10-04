"""SQLite helpers — stores data only; scoring stays in Python."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "flowline.db"

INCIDENT_COLUMNS = (
    "date",
    "company",
    "corridor",
    "substance",
    "release_m3",
    "incident_type",
    "cause",
    "latitude",
    "longitude",
    "consequence",
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  company TEXT,
  corridor TEXT,
  substance TEXT,
  release_m3 REAL,
  incident_type TEXT,
  cause TEXT,
  latitude REAL,
  longitude REAL,
  consequence TEXT,
  source TEXT DEFAULT 'cer_seed',
  loaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  corridor TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('inspect','escalate','defer')),
  priority TEXT CHECK (priority IN ('P1','P2','P3')),
  reason TEXT NOT NULL,
  policy_json TEXT NOT NULL,
  source TEXT NOT NULL
);
"""

_db_path_override: Path | None = None


def set_db_path(path: Path | None) -> None:
    """Test helper: redirect DB_PATH (None restores env/default)."""
    global _db_path_override
    _db_path_override = path


def db_path() -> Path:
    if _db_path_override is not None:
        return _db_path_override
    env = os.environ.get("DB_PATH")
    if env:
        path = Path(env)
        return path if path.is_absolute() else REPO_ROOT / path
    return DEFAULT_DB_PATH


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open one connection (caller closes). Row factory for dict-like access."""
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
