"""Postgres layer: schema, loader pieces, decisions, ranking parity, crew seeds.

Runs against a throwaway `flowline_test` database on the compose server; skipped
when the server is not reachable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import psycopg
import pytest

from core import crew_seed
from core.config import DEFAULT
from core.data import clear_load_cache
from core.scoring import score
from core.sites import assign_sites
from core.storage import append_decision, read_decisions
from scripts import load_postgres

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


def test_schema_is_idempotent(pg_env: str) -> None:
    with psycopg.connect(pg_env) as conn:
        load_postgres.apply_schema(conn)
        load_postgres.apply_schema(conn)
        names = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            )
        }
    for table in (
        "incidents",
        "incident_weather",
        "incident_embeddings",
        "corridors",
        "crew_types",
        "hazard_crew_map",
        "crew_bases",
        "decision_log",
        "pipelines",
    ):
        assert table in names


def test_ranking_from_postgres_matches_csv(
    pg_env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    clear_load_cache()
    from_csv = score(DEFAULT)
    monkeypatch.setenv("DATABASE_URL", pg_env)
    with load_postgres.connect(pg_env) as conn:
        n_seed, n_corridors = load_postgres.load_ranking(conn)
        conn.commit()
    clear_load_cache()
    from_pg = score(DEFAULT)
    assert n_seed == 313 and n_corridors > 100
    assert [r["corridor"] for r in from_pg] == [r["corridor"] for r in from_csv]
    assert [r["score"] for r in from_pg] == [r["score"] for r in from_csv]


def test_decisions_round_trip_postgres(
    pg_env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DECISIONS_BACKEND", "postgres")
    stored = append_decision(
        {
            "corridor": "Edson",
            "action": "escalate",
            "priority": "P1",
            "reason": "pg test",
            "policy": {"high": 6},
            "source": "planner",
        }
    )
    rows = [r for r in read_decisions() if r["id"] == stored["id"]]
    assert rows and rows[0]["policy"] == {"high": 6} and rows[0]["action"] == "escalate"
    with pytest.raises(ValueError):
        append_decision(
            {
                "corridor": "Edson",
                "action": "explode",
                "priority": "P1",
                "reason": "bad",
            }
        )


def test_crew_seed_never_overwrites_edits(pg_env: str) -> None:
    with load_postgres.connect(pg_env) as conn:
        load_postgres.seed_crews(conn)
        conn.execute(
            "UPDATE hazard_crew_map SET equipment = ARRAY['edited'] "
            "WHERE hazard_group = 'fire_ignition' AND crew_type_id = 'fire_response'"
        )
        types, mapping, bases = load_postgres.seed_crews(conn)
        row = conn.execute(
            "SELECT equipment, is_sample FROM hazard_crew_map "
            "WHERE hazard_group = 'fire_ignition' AND crew_type_id = 'fire_response'"
        ).fetchone()
        conn.rollback()
    assert row["equipment"] == ["edited"] and row["is_sample"] is True
    assert types == len(crew_seed.CREW_TYPES)
    assert bases == len(crew_seed.CREW_BASES)
    assert mapping == sum(len(v) for v in crew_seed.HAZARD_CREW_MAP.values())


def test_crew_seed_is_consistent() -> None:
    mapped = {
        crew for crews in crew_seed.HAZARD_CREW_MAP.values() for crew, _, _ in crews
    }
    at_bases = {c for *_, crews in crew_seed.CREW_BASES.values() for c in crews}
    assert mapped <= set(crew_seed.CREW_TYPES)
    assert at_bases <= set(crew_seed.CREW_TYPES)
    assert mapped <= at_bases  # every recommended crew exists at some base


def test_sites_group_close_points_without_chaining() -> None:
    # Three points 0.6 km apart in a line: leader clustering must not chain them all.
    lat = np.array([53.0, 53.0, 53.0, 54.0])
    lon = np.array([-116.0, -116.0 + 0.009, -116.0 + 0.018, -116.0])
    sites = assign_sites(lat, lon, radius_km=1.0)
    assert sites[0] == sites[1]
    assert sites[2] != sites[0]
    assert len(set(sites)) == 3


def test_sites_identical_coordinates_share_site() -> None:
    lat = np.array([55.1, 55.1, 55.1])
    lon = np.array([-118.8, -118.8, -118.8])
    assert len(set(assign_sites(lat, lon))) == 1
