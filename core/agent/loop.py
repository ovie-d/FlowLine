"""Tool-only agent loop over Gemini (with optional local Ollama fallback).

The model answers only via tool calls to core functions; every number in the final
answer is checked against tool results (core/agent/numbers.py). All calls go through
the budget guard (cache, usage log, spend cap). With no AI configured, the rest of
the app keeps working; only the briefing and chat are unavailable.
"""

from __future__ import annotations

import json
from typing import Any

from core.agent import llm
from core.agent.budget import BudgetExceeded, guarded_generate
from core.agent.numbers import unsupported_numbers
from core.agent.prompts import BRIEFING_INSTRUCTION, SYSTEM_PROMPT
from core.agent.tools import FORECAST_TOOL_NAMES, TOOL_SCHEMAS, dispatch_tool
from core.env import load_dotenv

MAX_TOOL_STEPS = 8
BRIEFING_MAX_STEPS = 3
UNAVAILABLE = {
    "answer": "The AI agent is unavailable right now; the forecast, map, routing and "
    "ranking still work.",
    "tool_calls": [],
    "error": True,
}


def _clients() -> list[llm.LLMClient]:
    return llm.configured_clients()


def _policy_system_suffix(policy: dict[str, Any]) -> str:
    if policy.get("count_only"):
        return (
            "The planner's dashboard is currently set to: count-only. "
            "Use this policy for every tool call unless the user explicitly asks "
            "for a different one, and say which policy you used."
        )
    high = policy.get("high", 3)
    medium = policy.get("medium", 1.5)
    low = policy.get("low", 1)
    return (
        f"The planner's dashboard is currently set to: high {high}x, "
        f"medium {medium}x, low {low}x. "
        "Use this policy for every tool call unless the user explicitly asks "
        "for a different one, and say which policy you used."
    )


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _generate(
    clients: list[llm.LLMClient],
    system: str,
    history: list[llm.Message],
    tools: list[dict[str, Any]],
    purpose: str,
) -> tuple[llm.LLMResponse, llm.LLMClient, bool]:
    """First provider that answers (Gemini, then Ollama)."""
    failures = []
    for client in clients:
        try:
            resp, cached = guarded_generate(
                client, system, history, tools, purpose=purpose
            )
            return resp, client, cached
        except llm.ProviderUnavailable as exc:
            failures.append(str(exc))
    raise llm.ProviderUnavailable("; ".join(failures) or "no provider configured")


def _tool_loop(
    clients: list[llm.LLMClient],
    system: str,
    messages: list[llm.Message],
    tools: list[dict[str, Any]],
    policy: dict[str, Any] | None,
    max_steps: int,
    purpose: str,
) -> dict[str, Any]:
    tool_calls: list[dict[str, Any]] = []
    usage = {
        "model_calls": 0,
        "cached_calls": 0,
        "prompt_tokens": 0,
        "output_tokens": 0,
    }
    answer, provider = "", None
    allowed = {t["name"] for t in tools}
    for _ in range(max_steps):
        resp, client, cached = _generate(clients, system, messages, tools, purpose)
        provider = {"provider": client.provider, "model": client.model}
        usage["model_calls"] += 1
        usage["cached_calls"] += int(cached)
        usage["prompt_tokens"] += resp.prompt_tokens
        usage["output_tokens"] += resp.output_tokens
        messages.append({"role": "model", "text": resp.text, "calls": resp.calls})
        if resp.text:
            answer = resp.text
        if not resp.calls:
            break
        results = []
        for call in resp.calls:
            if call["name"] in allowed:
                result = dispatch_tool(
                    call["name"], dict(call.get("args") or {}), policy=policy
                )
            else:
                result = {"error": f"Tool {call['name']} is not available here."}
            result = _json_safe(result)
            tool_calls.append(
                {
                    "name": call["name"],
                    "input": call.get("args") or {},
                    "result": result,
                }
            )
            results.append(
                {"id": call.get("id"), "name": call["name"], "response": result}
            )
        messages.append({"role": "tool", "results": results})
    else:
        if not answer:
            answer = "Stopped after the maximum number of tool steps. Ask a narrower question."
    return {
        "answer": answer,
        "tool_calls": tool_calls,
        "usage": usage,
        "provider": provider,
    }


def _finish(
    out: dict[str, Any], messages: list[llm.Message], evidence: list[Any], question: str
) -> dict[str, Any]:
    unsupported = unsupported_numbers(out["answer"], evidence, question)
    return {
        **out,
        "history": messages,
        "numbers_verified": not unsupported,
        "unsupported_numbers": unsupported,
    }


def run_agent(
    question: str,
    history: list[dict[str, Any]] | None = None,
    max_steps: int = MAX_TOOL_STEPS,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One chat turn. Returns {answer, tool_calls, history, numbers_verified, ...}."""
    load_dotenv()
    messages: list[llm.Message] = list(history or [])
    messages.append({"role": "user", "text": question})
    clients = _clients()
    if not clients:
        return {**UNAVAILABLE, "history": messages, "reason": llm.status()["reason"]}
    system = (
        SYSTEM_PROMPT
        if not policy
        else f"{SYSTEM_PROMPT}\n\n{_policy_system_suffix(policy)}"
    )
    try:
        out = _tool_loop(
            clients, system, messages, TOOL_SCHEMAS, policy, max_steps, "chat"
        )
    except BudgetExceeded as exc:
        return {
            "answer": str(exc),
            "tool_calls": [],
            "history": messages,
            "error": True,
            "budget_exceeded": True,
        }
    except llm.ProviderUnavailable as exc:
        return {**UNAVAILABLE, "history": messages, "reason": str(exc)}
    return _finish(out, messages, [t["result"] for t in out["tool_calls"]], question)


def run_briefing(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    corridor: str | None = None,
    start: str | None = None,
    operator_group: str | None = None,
) -> dict[str, Any]:
    """Readiness briefing for an area and week; every number comes from tool results."""
    load_dotenv()
    clients = _clients()
    if not clients:
        return {**UNAVAILABLE, "reason": llm.status()["reason"]}
    args = {
        k: v
        for k, v in {
            "latitude": latitude,
            "longitude": longitude,
            "corridor": corridor,
            "start": start,
            "operator_group": operator_group,
        }.items()
        if v is not None
    }
    readiness = _json_safe(dispatch_tool("get_readiness", args))
    if "error" in readiness:
        return {"answer": readiness["error"], "tool_calls": [], "error": True}
    place = (
        corridor
        or f"{readiness['forecast']['location']['latitude']:.3f}, "
        f"{readiness['forecast']['location']['longitude']:.3f}"
    )
    prompt = BRIEFING_INSTRUCTION.format(
        place=place,
        week_start=readiness["week"]["start"],
        week_end=readiness["week"]["end"],
        readiness_json=json.dumps(readiness, separators=(",", ":")),
    )
    messages: list[llm.Message] = [{"role": "user", "text": prompt}]
    tools = [t for t in TOOL_SCHEMAS if t["name"] in FORECAST_TOOL_NAMES]
    try:
        out = _tool_loop(
            clients,
            SYSTEM_PROMPT,
            messages,
            tools,
            None,
            BRIEFING_MAX_STEPS,
            "briefing",
        )
    except BudgetExceeded as exc:
        return {
            "answer": str(exc),
            "tool_calls": [],
            "error": True,
            "budget_exceeded": True,
        }
    except llm.ProviderUnavailable as exc:
        return {**UNAVAILABLE, "reason": str(exc)}
    seeded = {"name": "get_readiness", "input": args, "result": readiness}
    out["tool_calls"] = [seeded, *out["tool_calls"]]
    result = _finish(out, messages, [t["result"] for t in out["tool_calls"]], "")
    result.pop(
        "history", None
    )  # the prompt embeds the readiness JSON; keep payloads small
    result["readiness"] = readiness
    return result


def main() -> None:
    import sys

    out = run_agent(
        " ".join(sys.argv[1:]) or "What should I prepare for in Edson this week?"
    )
    print(out["answer"])
    print("\nTool calls:", [t["name"] for t in out.get("tool_calls", [])])
    if out.get("unsupported_numbers"):
        print("Unsupported numbers:", out["unsupported_numbers"])


if __name__ == "__main__":
    main()
