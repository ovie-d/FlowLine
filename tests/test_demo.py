"""Online demo: per-visitor sandbox, daily AI quota and budget cap, remote AI fallback."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg
import pytest
from fastapi.testclient import TestClient

from api import routes
from api.main import app
from core import crews, demo, remote_ai
from core.agent import budget, llm
from core.taxonomy import GEOTECHNICAL
from scripts import load_postgres

A = {"X-Flowline-Visitor": "visitor-aaaa1111"}
B = {"X-Flowline-Visitor": "visitor-bbbb2222"}
BRIEF = {"latitude": 53.58, "longitude": -116.44}


def fake_route(origin, incident) -> dict:
    return {
        "provider": "fake",
        "duration_min": 10.0,
        "distance_km": 10.0,
        "geometry": None,
        "last_mile": None,
        "warning": None,
        "fallbacks": [],
    }


@pytest.fixture
def demo_api(pg_env: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    with psycopg.connect(pg_env, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(
            "TRUNCATE crew_types, hazard_crew_map, crew_bases, crew_map_overrides, "
            "decision_log, ai_quota, ai_spend CASCADE"
        )
        load_postgres.seed_crews(conn)
        conn.commit()
    monkeypatch.setenv("FLOWLINE_DEMO", "1")
    monkeypatch.setenv("DECISIONS_BACKEND", "postgres")
    monkeypatch.setenv("AI_PROMPTS_PER_VISITOR", "3")
    monkeypatch.setenv("AI_PROMPTS_PER_IP", "10")
    monkeypatch.setenv("AI_DAILY_BUDGET_USD", "1.0")
    monkeypatch.setattr(crews, "route", fake_route)
    # A fake, always-available AI: no network, no spend.
    monkeypatch.setattr(llm, "status", lambda: {"available": True, "model": "fake"})
    monkeypatch.setattr(
        routes,
        "run_briefing",
        lambda **_: {"answer": "Briefing.", "tool_calls": [], "numbers_verified": True},
    )
    with TestClient(app) as client:
        yield client


def _log_spend(usd: float) -> None:
    budget.USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with budget.USAGE_LOG.open("a") as fh:
        ts = datetime.now(UTC).isoformat(timespec="seconds")
        fh.write(json.dumps({"ts": ts, "cost_usd": usd}) + "\n")


def test_three_ai_prompts_per_visitor_per_day(demo_api: TestClient) -> None:
    assert demo_api.get("/demo/status", headers=A).json()["remaining"] == 3
    for left in (2, 1, 0):
        out = demo_api.post("/briefing", json=BRIEF, headers=A).json()
        assert out["answer"] == "Briefing." and out["quota"]["remaining"] == left
    blocked = demo_api.post("/briefing", json=BRIEF, headers=A).json()
    assert blocked["error"] is True and "3 AI prompts" in blocked["reason"]
    # Another visitor still has their own 3.
    assert demo_api.get("/demo/status", headers=B).json()["remaining"] == 3
    assert "students" in demo_api.get("/demo/status", headers=B).json()["note"]


def test_shared_ip_cap_and_missing_visitor(demo_api: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AI_PROMPTS_PER_IP", "4")
    for _ in range(3):
        demo_api.post("/briefing", json=BRIEF, headers=A)
    demo_api.post("/briefing", json=BRIEF, headers=B)
    # Same client IP (the test client) has used 4: B is capped by the shared allowance.
    assert demo_api.post("/briefing", json=BRIEF, headers=B).json()["error"] is True
    no_id = demo_api.post("/briefing", json=BRIEF).json()
    assert no_id["error"] is True and "Reload" in no_id["reason"]


def test_daily_budget_cap_stops_everyone(demo_api: TestClient) -> None:
    demo.record_spend(0.6)
    assert (
        demo_api.get("/demo/status", headers=A).json()["daily_budget_reached"] is False
    )
    demo.record_spend(0.4)  # kept in the database: survives a server restart
    status = demo_api.get("/demo/status", headers=A).json()
    assert status["daily_budget_reached"] is True and status["remaining"] == 0
    out = demo_api.post("/briefing", json=BRIEF, headers=A).json()
    assert out["error"] is True and "budget" in out["reason"]


def test_usage_log_spend_also_counts(demo_api: TestClient) -> None:
    _log_spend(1.0)  # e.g. calls made before the database counter existed
    assert (
        demo_api.get("/demo/status", headers=A).json()["daily_budget_reached"] is True
    )


def test_failed_ai_call_gives_the_prompt_back(demo_api, monkeypatch) -> None:
    monkeypatch.setattr(
        routes, "run_briefing", lambda **_: {"answer": "", "error": True}
    )
    out = demo_api.post("/briefing", json=BRIEF, headers=A).json()
    assert out["quota"]["remaining"] == 3


def test_decisions_are_private_to_each_visitor(demo_api: TestClient) -> None:
    body = {"corridor": "Edson", "action": "escalate", "priority": "P1"}
    saved = demo_api.post("/decisions", json=body, headers=A).json()
    assert saved["corridor"] == "Edson"
    assert [d["corridor"] for d in demo_api.get("/decisions", headers=A).json()] == [
        "Edson"
    ]
    assert demo_api.get("/decisions", headers=B).json() == []
    bad = demo_api.post("/decisions", json={**body, "action": "delete"}, headers=A)
    assert bad.status_code == 422


def test_crew_edits_are_a_per_visitor_sandbox(
    demo_api: TestClient, pg_env: str
) -> None:
    edit = {
        "hazard_group": GEOTECHNICAL,
        "crews": [{"crew_type_id": "geotechnical", "equipment": ["Visitor A kit"]}],
    }
    assert demo_api.put("/crews/map", json=edit, headers=A).status_code == 200

    def geo(headers) -> list[dict]:
        hm = demo_api.get("/crews", headers=headers).json()["hazard_map"]
        return next(h for h in hm if h["hazard_group"] == GEOTECHNICAL)["crews"]

    assert geo(A) == [
        {**geo(A)[0], "crew_type_id": "geotechnical", "equipment": ["Visitor A kit"]}
    ]
    assert geo(A)[0]["is_sample"] is False
    assert all("Visitor A kit" not in c["equipment"] for c in geo(B))
    # The shared table is untouched.
    with psycopg.connect(pg_env) as conn:
        n = conn.execute(
            "SELECT count(*) FROM hazard_crew_map WHERE NOT is_sample"
        ).fetchone()[0]
    assert n == 0
    # Dispatch follows the visitor's own map.
    out = demo_api.post(
        "/dispatch/route",
        json={"latitude": 53.58, "longitude": -116.44, "hazard_group": GEOTECHNICAL},
        headers=A,
    ).json()
    assert all(
        [c["crew_type_id"] for c in b["matching_crews"]] == ["geotechnical"]
        for b in out["bases"]
    )


def test_local_install_is_unchanged(pg_env: str, monkeypatch) -> None:
    # No FLOWLINE_DEMO: no visitor scoping, no quota fields.
    monkeypatch.setenv("DECISIONS_BACKEND", "postgres")
    with TestClient(app) as client:
        assert client.get("/demo/status", headers=A).json() == {"demo": False}
        assert "quota" not in client.get("/agent/status", headers=A).json()
    assert demo.visitor() == ""


def test_remote_ai_used_when_no_local_key(monkeypatch) -> None:
    monkeypatch.setenv("FLOWLINE_REMOTE_AI", "https://demo.example/api")
    calls: list[tuple[str, dict]] = []

    def fake_forward(path: str, payload: dict) -> dict:
        calls.append((path, payload))
        return {"answer": "From the online demo.", "via_online_demo": True}

    monkeypatch.setattr(remote_ai, "forward", fake_forward)
    monkeypatch.setattr(
        remote_ai,
        "status",
        lambda: {"available": True, "model": "m", "quota": {"remaining": 2}},
    )
    with TestClient(app) as client:
        status = client.get("/agent/status").json()
        assert status["available"] is True and status["via_online_demo"] is True
        out = client.post("/briefing", json=BRIEF).json()
    assert out["answer"] == "From the online demo."
    assert calls[0][0] == "/briefing" and calls[0][1]["latitude"] == 53.58
