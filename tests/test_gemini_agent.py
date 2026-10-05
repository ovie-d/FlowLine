"""Gemini agent (mocked): conversion, tool-only numbers, budget guard, fallback, briefing."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import types

from api.main import app
from core.agent import budget, llm, loop
from core.agent.llm import GeminiClient, LLMResponse, OllamaClient
from core.agent.numbers import unsupported_numbers

FORECAST_RESULT = {
    "hazards": [
        {
            "label": "Ground movement, washout & geotechnical",
            "probability": 0.3612,
            "display": "36%",
            "alberta_share": 0.1185,
            "vs_alberta": 3.0,
        },
        {
            "label": "Equipment & component failure",
            "probability": 0.1876,
            "display": "19%",
        },
    ],
    "evidence": {"prior_incidents": 22},
    "low_evidence": False,
}


class FakeClient:
    """Scripted LLM: first asks for get_forecast, then answers with `final_text`."""

    provider = "gemini"
    model = "gemini-3.5-flash-lite"

    def __init__(self, final_text: str) -> None:
        self.final_text = final_text
        self.calls = 0

    def generate(self, system, history, tools):
        self.calls += 1
        if history[-1]["role"] == "tool":
            return LLMResponse(self.final_text, [], 1200, 80)
        call = {
            "id": "fc-1",
            "name": "get_forecast",
            "args": {"corridor": "Edson"},
            "signature": b"\x01sig",
        }
        return LLMResponse("", [call], 1000, 20)


@pytest.fixture
def fake_tools(monkeypatch: pytest.MonkeyPatch) -> list:
    seen = []

    def dispatch(name, args, policy=None):
        seen.append((name, args))
        return FORECAST_RESULT if name == "get_forecast" else {"error": "not mocked"}

    monkeypatch.setattr(loop, "dispatch_tool", dispatch)
    monkeypatch.setattr(loop, "load_dotenv", lambda: None)
    return seen


# ------------------------------------------------------------------ numbers


def test_numbers_from_tools_are_supported() -> None:
    answer = "Ground movement 36% (3.0× Alberta's 11.85%); 22 earlier incidents nearby."
    assert unsupported_numbers(answer, [FORECAST_RESULT]) == []


def test_invented_numbers_are_flagged() -> None:
    answer = "Ground movement is 41% and expected to rise 2.7× next week."
    assert unsupported_numbers(answer, [FORECAST_RESULT]) == ["41", "2.7"]


def test_small_wording_integers_and_question_numbers_allowed() -> None:
    assert (
        unsupported_numbers("Top 3 hazards for the next 7 days", [FORECAST_RESULT])
        == []
    )
    assert (
        unsupported_numbers("Within 25 km", [], question="what is within 25 km?") == []
    )


# ------------------------------------------------------------------ Gemini conversion


def test_gemini_contents_keep_thought_signature_and_tool_ids() -> None:
    history = [
        {"role": "user", "text": "hi"},
        {
            "role": "model",
            "text": "",
            "calls": [
                {
                    "id": "fc-1",
                    "name": "get_forecast",
                    "args": {"corridor": "Edson"},
                    "signature": b"\x01sig",
                }
            ],
        },
        {
            "role": "tool",
            "results": [{"id": "fc-1", "name": "get_forecast", "response": {"a": 1}}],
        },
    ]
    contents = GeminiClient.to_contents(history)
    assert [c.role for c in contents] == ["user", "model", "user"]
    call_part = contents[1].parts[0]
    assert call_part.thought_signature == b"\x01sig"
    assert call_part.function_call.id == "fc-1"
    resp = contents[2].parts[0].function_response
    assert resp.id == "fc-1" and resp.response == {"result": {"a": 1}}


def test_gemini_generate_request_and_parse() -> None:
    captured = {}

    class Models:
        def generate_content(self, model, contents, config):
            captured.update(model=model, config=config)
            return types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part(text="thinking…", thought=True),
                                types.Part(
                                    function_call=types.FunctionCall(
                                        id="x",
                                        name="get_forecast",
                                        args={"corridor": "Edson"},
                                    ),
                                    thought_signature=b"sig",
                                ),
                            ],
                        )
                    )
                ],
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=900,
                    candidates_token_count=40,
                    thoughts_token_count=60,
                ),
            )

    class SDK:
        models = Models()

    client = GeminiClient("key", "gemini-3.5-flash-lite", sdk_client=SDK())
    tools = [
        {
            "name": "get_forecast",
            "description": "d",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    out = client.generate("system", [{"role": "user", "text": "q"}], tools)
    cfg = captured["config"]
    assert captured["model"] == "gemini-3.5-flash-lite"
    assert cfg.max_output_tokens == llm.DEFAULT_MAX_OUTPUT_TOKENS
    assert cfg.automatic_function_calling.disable is True
    assert cfg.system_instruction == "system"
    assert cfg.tools[0].function_declarations[0].name == "get_forecast"
    assert out.text == ""  # thought text is not an answer
    assert out.calls[0]["signature"] == b"sig"
    assert (out.prompt_tokens, out.output_tokens) == (
        900,
        100,
    )  # thoughts billed as output


def test_gemini_api_error_is_provider_unavailable() -> None:
    from google.genai import errors

    class Models:
        def generate_content(self, **_):
            raise errors.APIError(503, {"error": {"message": "overloaded"}})

    class SDK:
        models = Models()

    with pytest.raises(llm.ProviderUnavailable):
        GeminiClient("k", "m", sdk_client=SDK()).generate(
            "s", [{"role": "user", "text": "q"}], []
        )


# ------------------------------------------------------------------ loop


def test_tool_only_answer_is_verified(monkeypatch, fake_tools) -> None:
    client = FakeClient(
        "Ground movement 36%, 3.0× the Alberta share; 22 earlier incidents."
    )
    monkeypatch.setattr(loop, "_clients", lambda: [client])
    out = loop.run_agent("What should Edson prepare for?")
    assert fake_tools == [("get_forecast", {"corridor": "Edson"})]
    assert out["numbers_verified"] is True and out["unsupported_numbers"] == []
    assert out["provider"] == {"provider": "gemini", "model": "gemini-3.5-flash-lite"}
    assert out["history"][1]["calls"][0]["signature"] == b"\x01sig"


def test_invented_number_in_answer_is_reported(monkeypatch, fake_tools) -> None:
    monkeypatch.setattr(
        loop, "_clients", lambda: [FakeClient("Washouts will hit 55% soon.")]
    )
    out = loop.run_agent("What should Edson prepare for?")
    assert out["numbers_verified"] is False and out["unsupported_numbers"] == ["55"]


def test_identical_requests_are_cached_and_logged(monkeypatch, fake_tools) -> None:
    client = FakeClient("Ground movement 36%.")
    monkeypatch.setattr(loop, "_clients", lambda: [client])
    loop.run_agent("Edson this week?")
    first_calls = client.calls
    out = loop.run_agent("Edson this week?")
    assert client.calls == first_calls  # served from the 10-minute cache
    assert out["usage"]["cached_calls"] == out["usage"]["model_calls"]
    log = [json.loads(line) for line in budget.USAGE_LOG.read_text().splitlines()]
    assert [e["cached"] for e in log] == [False, False, True, True]
    assert log[0]["cost_usd"] == budget.estimate_cost("gemini-3.5-flash-lite", 1000, 20)
    summary = budget.usage_summary()
    assert summary["calls"] == 4 and summary["cached_calls"] == 2
    assert summary["prompt_tokens"] == 2200 and summary["output_tokens"] == 100


def test_budget_cap_stops_calls(monkeypatch, fake_tools) -> None:
    monkeypatch.setenv("AGENT_BUDGET_USD", "0.0001")
    budget.USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    budget.USAGE_LOG.write_text(
        json.dumps({"provider": "gemini", "cost_usd": 0.01}) + "\n"
    )
    client = FakeClient("x")
    monkeypatch.setattr(loop, "_clients", lambda: [client])
    out = loop.run_agent("anything")
    assert out["budget_exceeded"] is True and client.calls == 0
    assert "AGENT_BUDGET_USD" in out["answer"]


def test_falls_back_to_ollama_when_gemini_unreachable(monkeypatch, fake_tools) -> None:
    class DownGemini(FakeClient):
        def generate(self, *a):
            raise llm.ProviderUnavailable("gemini: ConnectError")

    def ollama_api(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "llama-test" and body["messages"][0]["role"] == "system"
        if body["messages"][-1]["role"] == "tool":
            return httpx.Response(
                200,
                json={
                    "message": {"content": "Ground movement 36%."},
                    "prompt_eval_count": 50,
                    "eval_count": 9,
                },
            )
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_forecast",
                                "arguments": {"corridor": "Edson"},
                            }
                        }
                    ],
                }
            },
        )

    ollama = OllamaClient(
        "llama-test",
        "http://ollama.test",
        http=httpx.Client(transport=httpx.MockTransport(ollama_api)),
    )
    monkeypatch.setattr(loop, "_clients", lambda: [DownGemini("x"), ollama])
    out = loop.run_agent("Edson?")
    assert out["provider"]["provider"] == "ollama"
    assert out["answer"] == "Ground movement 36%." and out["numbers_verified"] is True


def test_briefing_uses_readiness_numbers(monkeypatch) -> None:
    readiness = {
        "week": {"start": "2026-10-05", "end": "2026-10-11"},
        "forecast": {
            "location": {"latitude": 53.58, "longitude": -116.44},
            **FORECAST_RESULT,
        },
        "recommended": [
            {
                "label": "Ground movement",
                "crews": [
                    {
                        "crew": "Geotechnical crew",
                        "nearest_base": {"base_name": "Edson", "duration_min": 10.2},
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(loop, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        loop,
        "dispatch_tool",
        lambda name, args, policy=None: readiness if name == "get_readiness" else {},
    )
    prompts = []

    class Writer(FakeClient):
        def generate(self, system, history, tools):
            prompts.append(history[0]["text"])
            assert {t["name"] for t in tools} <= set(loop.FORECAST_TOOL_NAMES)
            return LLMResponse(
                "Edson: ground movement 36%. Geotechnical crew at Edson, "
                "10.2 min (sample — to be validated).",
                [],
                900,
                60,
            )

    monkeypatch.setattr(loop, "_clients", lambda: [Writer("")])
    out = loop.run_briefing(corridor="Edson", start="2026-10-05")
    assert out["numbers_verified"] is True
    assert out["tool_calls"][0]["name"] == "get_readiness"
    assert '"display":"36%"' in prompts[0] and "2026-10-05 to 2026-10-11" in prompts[0]


# ------------------------------------------------------------------ API without a key


def test_api_without_key_degrades_cleanly() -> None:
    with TestClient(app) as client:
        status = client.get("/agent/status").json()
        brief = client.post("/briefing", json={"corridor": "Edson"}).json()
        usage = client.get("/agent/usage").json()
    assert status["available"] is False and "GEMINI_API_KEY" in status["reason"]
    assert brief["error"] is True and "forecast, map, routing" in brief["answer"]
    assert usage["budget_usd"] == budget.DEFAULT_BUDGET_USD


def test_status_prefers_gemini_then_ollama(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "llama-test")
    assert llm.status()["provider"] == "ollama"
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    s = llm.status()
    assert s["provider"] == "gemini" and s["fallback"] == "ollama"
