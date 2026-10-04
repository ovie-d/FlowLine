"""Smoke tests for the thin FastAPI layer (Somrit)."""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.sessions import clear_all


@pytest.fixture()
def client() -> TestClient:
    clear_all()
    with TestClient(app) as c:
        yield c
    clear_all()


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_ranking_high3_edson(client: TestClient) -> None:
    r = client.get("/ranking", params={"high": 3})
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]["corridor"] == "Edson"
    assert rows[0]["rank"] == 1


def test_ranking_high6_sherwood_park(client: TestClient) -> None:
    r = client.get("/ranking", params={"high": 6})
    assert r.status_code == 200
    assert r.json()[0]["corridor"] == "Sherwood Park"


def test_ranking_count_only_edson(client: TestClient) -> None:
    r = client.get("/ranking", params={"count_only": True})
    assert r.status_code == 200
    assert r.json()[0]["corridor"] == "Edson"


def test_ranking_high1_is_baseline(client: TestClient) -> None:
    r = client.get("/ranking", params={"high": 1})
    assert r.status_code == 200
    assert r.json()[0]["corridor"] == "Edson"


def test_triage_counts_high3(client: TestClient) -> None:
    r = client.get("/triage", params={"high": 3})
    assert r.status_code == 200
    assert r.json()["counts"] == {"escalate": 3, "inspect": 8, "defer": 4}


def test_triage_counts_high6(client: TestClient) -> None:
    r = client.get("/triage", params={"high": 6})
    assert r.status_code == 200
    assert r.json()["counts"] == {"escalate": 3, "inspect": 11, "defer": 1}


def test_corridor_jenner_low_confidence(client: TestClient) -> None:
    r = client.get("/corridor/Jenner")
    assert r.status_code == 200
    body = r.json()
    assert body["confidence_label"] == "High risk, low evidence base"


def test_corridor_unknown_404(client: TestClient) -> None:
    r = client.get("/corridor/nowhere")
    assert r.status_code == 404


def test_corridor_sherwood_park_operators(client: TestClient) -> None:
    r = client.get("/corridor/Sherwood Park")
    assert r.status_code == 200
    ops = {o["company"]: o["n"] for o in r.json()["operators"]}
    assert ops.get("Enbridge") == 10
    assert ops.get("Trans Mountain") == 6


def test_improvement_serious_events(client: TestClient) -> None:
    r = client.get("/improvement")
    assert r.status_code == 200
    body = r.json()
    stages = {s["stage"]: s for s in body["stages"]}
    assert stages["baseline"]["serious_captured"] == 62
    assert stages["ours"]["serious_captured"] == 68


def test_ranking_csv_filename(client: TestClient) -> None:
    r = client.get("/ranking.csv", params={"high": 6})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    cd = r.headers.get("content-disposition", "")
    assert "ranking_high6.csv" in cd
    text = r.text
    assert "rank,corridor,score" in text.splitlines()[0]


def test_negative_weight_422(client: TestClient) -> None:
    r = client.get("/ranking", params={"high": -1})
    assert r.status_code == 422


def test_assumptions_and_decisions(client: TestClient) -> None:
    a = client.get("/assumptions")
    assert a.status_code == 200
    assert isinstance(a.json(), list)
    d = client.get("/decisions")
    assert d.status_code == 200
    assert isinstance(d.json(), list)


def test_compare(client: TestClient) -> None:
    r = client.post(
        "/compare",
        json={
            "a": {"high": 3, "medium": 1.5, "low": 1},
            "b": {"high": 6, "medium": 1.5, "low": 1},
            "top": 15,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "movers" in body
    assert body["top_a"][0]["corridor"] == "Edson"
    assert body["top_b"][0]["corridor"] == "Sherwood Park"


def test_agent_without_key_does_not_break_ranking(client: TestClient) -> None:
    prev = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        agent = client.post(
            "/agent",
            json={"session_id": "smoke", "question": "Triage the top 15"},
        )
        assert agent.status_code == 200
        body = agent.json()
        assert body.get("error") is True
        assert "history" not in body
        assert isinstance(body.get("tool_calls"), list)

        ranking = client.get("/ranking", params={"high": 3})
        assert ranking.status_code == 200
        assert ranking.json()[0]["corridor"] == "Edson"
    finally:
        if prev is not None:
            os.environ["ANTHROPIC_API_KEY"] = prev


def test_agent_reset(client: TestClient) -> None:
    r = client.post("/agent/reset", json={"session_id": "smoke"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_ranking_field_passthrough(client: TestClient) -> None:
    row: dict[str, Any] = client.get("/ranking", params={"high": 3}).json()[0]
    for key in (
        "rank",
        "corridor",
        "score",
        "likelihood",
        "consequence",
        "n",
        "n_high",
        "n_medium",
        "n_low",
        "confidence",
        "drivers",
        "operator",
        "lat",
        "lon",
        "last_incident",
    ):
        assert key in row
