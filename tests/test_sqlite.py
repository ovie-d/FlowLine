"""SQLite storage + incident load parity (math stays in Python)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from core.config import CONSEQUENCE_HEAVY, DEFAULT
from core.data import DATA_PATH, clear_load_cache, load_incidents
from core.db import set_db_path
from core.scoring import score
from core.storage import append_decision, read_decisions, set_decisions_path
from scripts.load_incidents import load_seed


@pytest.fixture()
def sqlite_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "flowline.db"
    decisions_json = tmp_path / "inspection_decisions.json"
    set_db_path(db)
    set_decisions_path(decisions_json)
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.delenv("DECISIONS_BACKEND", raising=False)
    clear_load_cache()
    yield db
    clear_load_cache()
    set_db_path(None)
    set_decisions_path(None)
    monkeypatch.delenv("DECISIONS_BACKEND", raising=False)


def test_load_incidents_script_inserts_313(sqlite_env: Path) -> None:
    n = load_seed(database=sqlite_env)
    assert n == 313
    assert sqlite_env.exists()


def test_db_cleaned_matches_csv(sqlite_env: Path) -> None:
    load_seed(database=sqlite_env)

    set_db_path(sqlite_env.parent / "missing.db")
    clear_load_cache()
    csv_clean, csv_report = load_incidents(DEFAULT)
    assert csv_report["source"].startswith("csv:")
    assert csv_report["rows_loaded"] == 313

    set_db_path(sqlite_env)
    clear_load_cache()
    db_clean, db_report = load_incidents(DEFAULT)
    assert db_report["source"].startswith("db:")
    assert db_report["rows_loaded"] == 313

    cols = [
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
    ]
    left = csv_clean[cols].sort_values(cols).reset_index(drop=True)
    right = db_clean[cols].sort_values(cols).reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right, check_dtype=False)

    # Raw seed count parity.
    assert len(pd.read_csv(DATA_PATH)) == 313


def test_score_from_db_matches_csv(sqlite_env: Path) -> None:
    load_seed(database=sqlite_env)

    set_db_path(sqlite_env.parent / "nope.db")
    clear_load_cache()
    csv_default = score(DEFAULT, top=15)
    csv_heavy = score(CONSEQUENCE_HEAVY, top=15)

    set_db_path(sqlite_env)
    clear_load_cache()
    db_default = score(DEFAULT, top=15)
    db_heavy = score(CONSEQUENCE_HEAVY, top=15)

    assert csv_default[0]["corridor"] == "Edson"
    assert db_default[0]["corridor"] == "Edson"
    assert csv_heavy[0]["corridor"] == "Sherwood Park"
    assert db_heavy[0]["corridor"] == "Sherwood Park"
    assert [r["corridor"] for r in csv_default] == [r["corridor"] for r in db_default]
    assert [r["score"] for r in csv_default] == [r["score"] for r in db_default]


def test_sqlite_decisions_round_trip(
    sqlite_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECISIONS_BACKEND", "sqlite")
    load_seed(database=sqlite_env)
    stored = append_decision(
        {
            "corridor": "Sherwood Park",
            "action": "escalate",
            "priority": "P1",
            "reason": "sqlite demo",
            "policy": {"high": 6.0, "medium": 1.5, "low": 1.0},
            "source": "planner",
        }
    )
    assert isinstance(stored["policy"], dict)
    rows = read_decisions()
    assert len(rows) == 1
    assert rows[0]["corridor"] == "Sherwood Park"
    assert rows[0]["policy"] == {"high": 6.0, "medium": 1.5, "low": 1.0}
    assert rows[0]["action"] == "escalate"


def test_sqlite_bad_action_rejected(
    sqlite_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECISIONS_BACKEND", "sqlite")
    load_seed(database=sqlite_env)
    with pytest.raises(ValueError):
        append_decision(
            {
                "corridor": "Edson",
                "action": "ignore",
                "priority": "P1",
                "reason": "bad",
            }
        )


def test_default_backend_still_json(
    sqlite_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DECISIONS_BACKEND", raising=False)
    load_seed(database=sqlite_env)
    append_decision(
        {
            "corridor": "Edson",
            "action": "inspect",
            "priority": "P2",
            "reason": "json path",
            "policy": {"high": 3},
            "source": "planner",
        }
    )
    assert read_decisions()[0]["reason"] == "json path"
    with sqlite3.connect(sqlite_env) as conn:
        n = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    assert n == 0
