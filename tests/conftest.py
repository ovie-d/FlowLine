"""Shared test isolation: never touch the developer's Postgres or decision log."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    # Empty (not deleted) so core.env.load_dotenv() cannot fill them from .env.
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DECISIONS_BACKEND", "json")
