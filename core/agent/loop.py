"""Thin Anthropic tool loop over core agent tools."""

from __future__ import annotations

import json
import os
from typing import Any

from core.agent.prompts import SYSTEM_PROMPT
from core.agent.tools import TOOL_SCHEMAS, dispatch_tool
from core.env import load_dotenv

MAX_TOOL_STEPS = 8
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
UNAVAILABLE = {
    "answer": "The agent is unavailable right now; the ranking still works.",
    "tool_calls": [],
    "error": True,
}


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("anthropic package required for the agent loop") from exc
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


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


def run_agent(
    question: str,
    history: list[dict[str, Any]] | None = None,
    max_steps: int = MAX_TOOL_STEPS,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one user turn. Returns {answer, tool_calls, history}.

    Optional ``policy`` (e.g. ``{"high": 6}`` or ``{"count_only": True}``) is
    injected into the system prompt and merged into tool calls when the model
    omits its own config overrides.
    """
    load_dotenv()
    messages: list[dict[str, Any]] = list(history or [])
    messages.append({"role": "user", "content": question})

    try:
        client = _client()
    except Exception as exc:  # noqa: BLE001
        _ = exc
        return {**UNAVAILABLE, "history": messages}

    model = os.environ.get("AGENT_MODEL", DEFAULT_MODEL)
    tool_calls: list[dict[str, Any]] = []
    answer = ""
    system = SYSTEM_PROMPT
    if policy:
        system = f"{SYSTEM_PROMPT}\n\n{_policy_system_suffix(policy)}"

    try:
        for _ in range(max_steps):
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            assistant_content = response.content
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        block.model_dump(exclude_none=True)
                        if hasattr(block, "model_dump")
                        else dict(block)
                        for block in assistant_content
                    ],
                }
            )

            uses = [
                b for b in assistant_content if getattr(b, "type", None) == "tool_use"
            ]
            texts = [
                getattr(b, "text", "")
                for b in assistant_content
                if getattr(b, "type", None) == "text"
            ]
            if texts:
                answer = "\n".join(t for t in texts if t)

            if response.stop_reason == "end_turn" or not uses:
                break

            tool_results = []
            for use in uses:
                name = use.name
                args = use.input if isinstance(use.input, dict) else {}
                result = dispatch_tool(name, args, policy=policy)
                tool_calls.append({"name": name, "input": args, "result": result})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": use.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
        else:
            if not answer:
                answer = (
                    "Stopped after maximum tool steps. "
                    "Ask a narrower question or raise the consequence weight and retry."
                )
    except Exception as exc:  # noqa: BLE001
        _ = exc
        return {**UNAVAILABLE, "history": messages}

    return {"answer": answer, "tool_calls": tool_calls, "history": messages}


def main() -> None:
    import sys

    args = sys.argv[1:]
    if args:
        msg = " ".join(args)
        out = run_agent(msg)
        print(out["answer"])
        if out.get("error"):
            print("\n(agent unavailable)")
        else:
            print("\nTool calls:", [t["name"] for t in out["tool_calls"]])
        return

    history: list[dict[str, Any]] = []
    print("Pipeline risk agent. Type a question, or exit/quit to stop.")
    try:
        while True:
            try:
                msg = input("> ").strip()
            except EOFError:
                print()
                break
            if not msg:
                continue
            if msg.lower() in {"exit", "quit"}:
                break
            out = run_agent(msg, history)
            history = out.get("history") or history
            print(out["answer"])
            if out.get("error"):
                print("\n(agent unavailable)")
            else:
                print("\nTool calls:", [t["name"] for t in out["tool_calls"]])
            print()
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
