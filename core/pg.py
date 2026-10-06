"""PostgreSQL connection helpers (psycopg 3). DATABASE_URL selects the database."""

from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row

CONNECT_TIMEOUT_S = 3


def database_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "").strip()
    return url or None


def connect(url: str | None = None, **kwargs: object) -> psycopg.Connection:
    """Open a connection (caller closes). Rows come back as dicts."""
    target = url or database_url()
    if not target:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(
        target, connect_timeout=CONNECT_TIMEOUT_S, row_factory=dict_row, **kwargs
    )


def try_connect(url: str | None = None) -> psycopg.Connection | None:
    """Connection, or None when no URL is set or the server is unreachable."""
    if not (url or database_url()):
        return None
    try:
        return connect(url)
    except psycopg.OperationalError:
        return None
