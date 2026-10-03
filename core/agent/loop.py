"""Thin Anthropic tool loop over core agent tools."""

from __future__ import annotations

import json
import os
from typing import Any

from core.agent.prompts import SYSTEM_PROMPT
from core.agent.tools import TOOL_SCHEMAS, dispatch_tool

MAX_TOOL_STEPS = 8


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("anthropic package required for the agent loop") from exc
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def run_agent(
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one user turn. Returns {answer, tool_calls, history}."""
    client = _client()
    model = os.environ.get("AGENT_MODEL", "claude-sonnet-4-20250514")

    messages: list[dict[str, Any]] = list(history or [])
    messages.append({"role": "user", "content": message})

    tool_calls: list[dict[str, Any]] = []
    answer = ""

    for _ in range(MAX_TOOL_STEPS):
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
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

        uses = [b for b in assistant_content if getattr(b, "type", None) == "tool_use"]
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
            result = dispatch_tool(name, args)
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

    return {"answer": answer, "tool_calls": tool_calls, "history": messages}


def main() -> None:
    import sys

    msg = " ".join(sys.argv[1:]) or "What is the top corridor under high=6?"
    out = run_agent(msg)
    print(out["answer"])
    print("\nTool calls:", [t["name"] for t in out["tool_calls"]])


if __name__ == "__main__":
    main()
