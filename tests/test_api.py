"""Smoke tests for the thin FastAPI layer (Somrit)."""

from __future__ import annotations

import json
from pathlib import Path
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


def test_improvement_for_high_query(client: TestClient) -> None:
    r = client.get("/improvement", params={"high": 6})
    assert r.status_code == 200
    body = r.json()
    assert body["serious_total"] == 123
    assert body["current"]["serious_captured"] == 69
    assert body["current"]["incidents_covered"] == 154
    assert body["baseline"]["serious_captured"] == 62
    assert body["baseline"]["incidents_covered"] == 169
    assert body["policy"]["high"] == 6.0


def test_agent_forwards_high_as_policy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake_run(question, history=None, max_steps=8, policy=None):
        seen["policy"] = policy
        history = list(history or [])
        history.append({"role": "user", "content": question})
        return {
            "answer": "ok",
            "tool_calls": [],
            "history": history,
        }

    monkeypatch.setattr("api.routes.run_agent", fake_run)
    r = client.post(
        "/agent",
        json={"session_id": "pol", "question": "Explain Sherwood Park", "high": 6},
    )
    assert r.status_code == 200
    assert seen["policy"] == {"high": 6}

    r2 = client.post(
        "/agent",
        json={"session_id": "pol2", "question": "Triage", "high": 1},
    )
    assert r2.status_code == 200
    assert seen["policy"] == {"count_only": True}


def test_ranking_csv_filename(client: TestClient) -> None:
    r = client.get("/ranking.csv", params={"high": 6})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "charset=utf-8" in r.headers["content-type"]
    cd = r.headers.get("content-disposition", "")
    assert "ranking_high6.csv" in cd
    # utf-8-sig BOM for Excel
    assert r.content.startswith(b"\xef\xbb\xbf")
    text = r.content.decode("utf-8-sig")
    assert "rank,corridor,score" in text.splitlines()[0]


def test_ranking_json_declares_utf8(client: TestClient) -> None:
    r = client.get("/ranking", params={"high": 3})
    assert r.status_code == 200
    assert "charset=utf-8" in r.headers["content-type"]


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


def test_agent_without_key_does_not_break_ranking(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pop alone is not enough: run_agent() calls load_dotenv(), which reloads
    # ANTHROPIC_API_KEY from the local .env file.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("core.agent.loop.load_dotenv", lambda *args, **kwargs: None)

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


def test_agent_reset(client: TestClient) -> None:
    r = client.post("/agent/reset", json={"session_id": "smoke"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_agent_tool_calls_are_slim(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(question: str, history=None, max_steps=8, policy=None):
        history = list(history or [])
        history.append({"role": "user", "content": question})
        return {
            "answer": "Triage draft ready.",
            "tool_calls": [
                {
                    "name": "auto_triage",
                    "input": {"top": 15},
                    "result": {"drafts": [{"corridor": "x"}] * 50, "pad": "y" * 4000},
                }
            ],
            "history": history
            + [{"role": "assistant", "content": "Triage draft ready."}],
        }

    monkeypatch.setattr("api.routes.run_agent", fake_run)
    r = client.post(
        "/agent",
        json={"session_id": "slim", "question": "Triage the top 15"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) <= {"answer", "tool_calls", "error"}
    assert "history" not in body
    assert len(body["tool_calls"]) == 1
    assert body["tool_calls"][0] == {"name": "auto_triage", "input": {"top": 15}}
    assert "result" not in body["tool_calls"][0]
    assert len(json.dumps(body)) < 2000


def test_agent_multi_turn_logs_decision(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from core.storage import append_decision, read_decisions, set_decisions_path

    set_decisions_path(tmp_path / "decisions.json")
    monkeypatch.setattr("api.sessions.clear_all", lambda: None)

    def fake_run(question: str, history=None, max_steps=8, policy=None):
        history = list(history or [])
        history.append({"role": "user", "content": question})
        q = question.lower()
        if "escalate" in q:
            append_decision(
                {
                    "corridor": "Sherwood Park",
                    "action": "escalate",
                    "priority": "P1",
                    "reason": "planner approved via chat",
                    "policy": {"high": 3},
                    "source": "planner",
                }
            )
            answer = "Logged escalate for Sherwood Park."
            calls = [
                {
                    "name": "log_decision",
                    "input": {
                        "corridor": "Sherwood Park",
                        "action": "escalate",
                        "priority": "P1",
                    },
                    "result": {"ok": True, "id": "x"},
                }
            ]
        else:
            answer = "Triage complete."
            calls = [
                {
                    "name": "auto_triage",
                    "input": {"top": 15},
                    "result": {"counts": {"escalate": 3}},
                }
            ]
        history.append({"role": "assistant", "content": answer})
        return {"answer": answer, "tool_calls": calls, "history": history}

    monkeypatch.setattr("api.routes.run_agent", fake_run)

    first = client.post(
        "/agent",
        json={"session_id": "multi", "question": "Triage the top 15"},
    )
    assert first.status_code == 200
    assert first.json()["tool_calls"][0]["name"] == "auto_triage"
    assert set(first.json()["tool_calls"][0].keys()) == {"name", "input"}

    second = client.post(
        "/agent",
        json={
            "session_id": "multi",
            "question": "Escalate Sherwood Park, P1",
        },
    )
    assert second.status_code == 200
    assert set(second.json().keys()) <= {"answer", "tool_calls", "error"}
    assert second.json()["tool_calls"][0] == {
        "name": "log_decision",
        "input": {
            "corridor": "Sherwood Park",
            "action": "escalate",
            "priority": "P1",
        },
    }
    rows = read_decisions()
    assert len(rows) == 1
    assert rows[0]["corridor"] == "Sherwood Park"
    assert rows[0]["action"] == "escalate"
    set_decisions_path(None)


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
