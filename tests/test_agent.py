"""Agent / storage / triage tests — no API key required."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from core.agent.loop import run_agent
from core.agent.tools import TOOL_FUNCTIONS, dispatch_tool, log_decision
from core.assumptions import get_assumptions
from core.config import CONSEQUENCE_HEAVY, DEFAULT
from core.labels import LOW_CONFIDENCE_LABEL
from core.scoring import explain_corridor
from core.storage import append_decision, read_decisions, set_decisions_path
from core.triage import BANNED_REASON_SNIPPETS, ESCALATE_MIN_HIGH, draft_triage

OLD_ASSUMPTION_IDS = {
    "volume_vs_severity",
    "facility_events",
    "gas_threshold",
    "injuries_medium",
    "edmonton_sherwood",
    "triage_escalate_min_high",
}


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
    assert jenner["reason"].startswith(LOW_CONFIDENCE_LABEL)

    by_name = {d["corridor"]: d for d in result["drafts"]}
    for name in ("Sherwood Park", "Edmonton", "Hardisty"):
        assert by_name[name]["action"] == "escalate"
        assert by_name[name]["priority"] == "P1"
    assert by_name["Edson"]["action"] == "inspect"
    assert by_name["Edson"]["action"] != "escalate"


def test_plain_english_reasons():
    result = draft_triage(DEFAULT, top=15)
    edson = next(d for d in result["drafts"] if d["corridor"] == "Edson")
    assert "33 incidents" in edson["reason"]
    assert "2 high-consequence" in edson["reason"]

    jenner = next(d for d in result["drafts"] if d["corridor"] == "Jenner")
    assert jenner["reason"].startswith(LOW_CONFIDENCE_LABEL)

    fort_mckay = next(d for d in result["drafts"] if d["corridor"] == "Fort McKay")
    # Space after comma between type counts (on-screen copy).
    assert "environmental effects (5), fires (2)" in fort_mckay["reason"]

    for d in result["drafts"]:
        assert d["reason"]
        assert re.search(r"\d", d["reason"])
        lowered = d["reason"].lower()
        for banned in BANNED_REASON_SNIPPETS:
            assert banned not in lowered, (d["corridor"], d["reason"], banned)
        assert "),(" not in d["reason"].replace(" ", "")


def test_confidence_label_on_explain():
    jenner = explain_corridor("Jenner")
    assert jenner["confidence_label"] == LOW_CONFIDENCE_LABEL
    edson = explain_corridor("Edson")
    assert edson["confidence_label"] is None


def test_mentor_assumption_statuses():
    rows = {a["id"]: a for a in get_assumptions()}
    assert OLD_ASSUMPTION_IDS <= set(rows)
    assert rows["volume_vs_severity"]["status"] == "validated"
    assert rows["facility_events"]["status"] == "validated"
    assert rows["gas_threshold"]["status"] == "validated"
    assert rows["edmonton_sherwood"]["status"] == "validated"
    assert rows["triage_escalate_min_high"]["status"] == "unvalidated"
    assert (
        "pipeline integrity professional"
        in rows["volume_vs_severity"]["evidence"].lower()
    )


def test_escalate_set_stable_across_heavy_policy():
    default_set = {
        d["corridor"]
        for d in draft_triage(DEFAULT, top=15)["drafts"]
        if d["action"] == "escalate"
    }
    heavy_set = {
        d["corridor"]
        for d in draft_triage(CONSEQUENCE_HEAVY, top=15)["drafts"]
        if d["action"] == "escalate"
    }
    expected = {"Sherwood Park", "Edmonton", "Hardisty"}
    assert default_set == heavy_set == expected


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


def test_run_agent_no_key_returns_error_payload(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Empty/missing .env must not invent a key.
    monkeypatch.setattr("core.agent.loop.load_dotenv", lambda: None)
    out = run_agent("Explain Sherwood Park")
    assert out.get("error") is True
    assert out["tool_calls"] == []
    assert "unavailable" in out["answer"].lower()
    assert "ranking still works" in out["answer"].lower()


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    from core.env import load_dotenv

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-test-123\nAGENT_MODEL=claude-haiku-4-5-20251001\n"
    )
    load_dotenv(env_file)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test-123"
    assert os.environ["AGENT_MODEL"] == "claude-haiku-4-5-20251001"


def test_log_decision_tool_bad_action_returns_error(decisions_file: Path):
    out = log_decision("Edson", "noop", "P1", "x")
    assert "error" in out


def test_dispatch_policy_merges_for_explain():
    result = dispatch_tool(
        "explain_corridor",
        {"name": "Sherwood Park"},
        policy={"high": 6},
    )
    assert result["rank"] == 1
    assert result["score"] == 48.0


def test_dispatch_no_policy_default_rank():
    result = dispatch_tool("explain_corridor", {"name": "Sherwood Park"})
    assert result["rank"] == 2
    assert result["score"] == 30.0


def test_dispatch_own_high_not_overridden_by_policy():
    result = dispatch_tool(
        "explain_corridor",
        {"name": "Sherwood Park", "config_overrides": {"high": 3}},
        policy={"high": 6},
    )
    assert result["rank"] == 2
    assert result["score"] == 30.0


def test_log_decision_inherits_dashboard_policy(decisions_file: Path):
    result = dispatch_tool(
        "log_decision",
        {
            "corridor": "Sherwood Park",
            "action": "escalate",
            "priority": "P1",
            "reason": "planner approved under slider",
        },
        policy={"high": 6},
    )
    assert result.get("ok") is True
    assert result["logged"]["policy"]["high"] == 6


def test_run_agent_passes_policy_into_dispatch(monkeypatch, decisions_file: Path):
    """Mock Anthropic: one tool_use then end_turn; policy must reach dispatch."""
    seen: dict[str, object] = {}

    class _Block:
        type = "tool_use"
        name = "explain_corridor"
        id = "tu_1"
        input = {"name": "Sherwood Park"}

        def model_dump(self, exclude_none=True):
            return {
                "type": self.type,
                "name": self.name,
                "id": self.id,
                "input": self.input,
            }

    class _Response:
        def __init__(self, stop_reason, content):
            self.stop_reason = stop_reason
            self.content = content

    class _Messages:
        def create(self, **kwargs):
            seen["system"] = kwargs.get("system", "")
            if seen.get("calls"):
                return _Response("end_turn", [])
            seen["calls"] = 1
            return _Response("tool_use", [_Block()])

    class _Client:
        messages = _Messages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr("core.agent.loop.load_dotenv", lambda: None)
    monkeypatch.setattr("core.agent.loop._client", lambda: _Client())

    real_dispatch = dispatch_tool

    def tracking_dispatch(name, arguments, policy=None):
        seen["dispatch_policy"] = policy
        return real_dispatch(name, arguments, policy=policy)

    monkeypatch.setattr("core.agent.loop.dispatch_tool", tracking_dispatch)

    out = run_agent("Explain Sherwood Park", policy={"high": 6})
    assert seen["dispatch_policy"] == {"high": 6}
    assert "high 6x" in str(seen["system"]).lower().replace("×", "x")
    assert out["tool_calls"]
    assert out["tool_calls"][0]["result"]["rank"] == 1
    assert out["tool_calls"][0]["result"]["score"] == 48.0
