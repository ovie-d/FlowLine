"""Agent / storage / triage tests — no API key required."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.agent.loop import run_agent
from core.agent.tools import TOOL_FUNCTIONS, dispatch_tool, log_decision
from core.config import DEFAULT
from core.storage import append_decision, read_decisions, set_decisions_path
from core.triage import ESCALATE_MIN_HIGH, draft_triage


@pytest.fixture
def decisions_file(tmp_path: Path):
    path = tmp_path / "inspection_decisions.json"
    set_decisions_path(path)
    yield path
    set_decisions_path(None)


def test_storage_round_trip(decisions_file: Path):
    stored = append_decision(
        {
            "corridor": "Sherwood Park",
            "action": "escalate",
            "priority": "P1",
            "reason": "demo",
            "policy": {"high": 6},
            "source": "planner",
        }
    )
    assert stored["id"]
    assert stored["policy"] == {"high": 6}
    assert stored["source"] == "planner"
    rows = read_decisions()
    assert len(rows) == 1
    assert rows[0]["corridor"] == "Sherwood Park"
    assert decisions_file.exists()


def test_storage_bad_action_raises(decisions_file: Path):
    with pytest.raises(ValueError):
        append_decision(
            {
                "corridor": "Edson",
                "action": "ignore",
                "priority": "P1",
                "reason": "bad",
            }
        )


def test_draft_triage_shape_and_jenner():
    result = draft_triage(DEFAULT, top=15)
    json.dumps(result)
    assert len(result["drafts"]) == 15
    assert sum(result["counts"].values()) == 15

    jenner = next(d for d in result["drafts"] if d["corridor"] == "Jenner")
    assert jenner["action"] == "inspect"
    assert jenner["priority"] == "P3"
    assert "thin data" in jenner["reason"].lower()

    by_name = {d["corridor"]: d for d in result["drafts"]}
    for name in ("Sherwood Park", "Edmonton", "Hardisty"):
        assert by_name[name]["action"] == "escalate"
        assert by_name[name]["priority"] == "P1"
    assert by_name["Edson"]["action"] == "inspect"
    assert by_name["Edson"]["action"] != "escalate"


def test_r1_escalates_when_n_high_ge_threshold():
    result = draft_triage(DEFAULT, top=15)
    for d in result["drafts"]:
        if d["n_high"] >= ESCALATE_MIN_HIGH and d["confidence"] == "ok":
            assert d["action"] == "escalate"
            assert d["rule"] == "R1"


def test_dispatch_all_six_tools(decisions_file: Path):
    assert set(TOOL_FUNCTIONS) == {
        "get_ranking",
        "explain_corridor",
        "compare",
        "get_assumptions",
        "auto_triage",
        "log_decision",
    }
    ranking = dispatch_tool("get_ranking", {"top": 3})
    assert isinstance(ranking, list) and ranking[0]["corridor"]

    explained = dispatch_tool("explain_corridor", {"name": "Edson"})
    assert explained["corridor"] == "Edson"

    compared = dispatch_tool(
        "compare", {"a": {"count_only": True}, "b": {"high": 6}, "top": 5}
    )
    assert "overlap" in compared

    assumptions = dispatch_tool("get_assumptions", {})
    assert any(a["id"] == "triage_escalate_min_high" for a in assumptions)

    triage = dispatch_tool("auto_triage", {"top": 15})
    assert len(triage["drafts"]) == 15

    logged = dispatch_tool(
        "log_decision",
        {
            "corridor": "Sherwood Park",
            "action": "escalate",
            "priority": "P1",
            "reason": "planner approved",
            "policy": {"high": 6},
        },
    )
    assert logged.get("ok") is True
    assert logged["logged"]["policy"] == {"high": 6}
    assert logged["logged"]["source"] == "planner"

    unknown = dispatch_tool("not_a_tool", {})
    assert "error" in unknown


def test_run_agent_no_key_returns_error_payload(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = run_agent("Explain Sherwood Park")
    assert out.get("error") is True
    assert out["tool_calls"] == []
    assert "unavailable" in out["answer"].lower()
    assert "ranking still works" in out["answer"].lower()


def test_log_decision_tool_bad_action_returns_error(decisions_file: Path):
    out = log_decision("Edson", "noop", "P1", "x")
    assert "error" in out
