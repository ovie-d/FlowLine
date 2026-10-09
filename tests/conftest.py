"""Shared test isolation: never touch the developer's Postgres or decision log."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from core.data import clear_load_cache
from scripts import load_postgres


@pytest.fixture(autouse=True)
def _isolate_backends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Empty (not deleted) so core.env.load_dotenv() cannot fill them from .env.
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DECISIONS_BACKEND", "json")
    # Never call a real (billed) LLM from tests, never touch the real usage log.
    for var in ("GEMINI_API_KEY", "GEMINI_MODEL", "OLLAMA_MODEL", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(var, "")
    # Online-demo settings (quota, sandbox, remote AI) are opt-in per test.
    for var in ("FLOWLINE_DEMO", "FLOWLINE_REMOTE_AI"):
        monkeypatch.setenv(var, "")
    from core.agent import budget

    monkeypatch.setattr(budget, "USAGE_LOG", tmp_path / "agent_usage.jsonl")
    budget.clear_cache()


ROOT = Path(__file__).resolve().parent.parent
TEST_DB = "flowline_test"


def _base_url() -> str:
    url = os.environ.get("FLOWLINE_TEST_PG", "")
    if url:
        return url
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return "postgresql://flowline:flowline@localhost:5432/flowline"


def _with_db(url: str, name: str) -> str:
    return url.rsplit("/", 1)[0] + "/" + name


@pytest.fixture(scope="module")
def test_db_url() -> Iterator[str]:
    base = _base_url()
    try:
        with psycopg.connect(
            _with_db(base, "postgres"), autocommit=True, connect_timeout=2
        ) as c:
            exists = c.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
            ).fetchone()
            if not exists:
                c.execute(f"CREATE DATABASE {TEST_DB}")
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (docker compose up -d db)")
    url = _with_db(base, TEST_DB)
    with psycopg.connect(url) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        conn.commit()
    yield url


@pytest.fixture
def pg_env(test_db_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    with psycopg.connect(test_db_url) as conn:
        load_postgres.apply_schema(conn)
        conn.commit()
    clear_load_cache()
    yield test_db_url
    clear_load_cache()
