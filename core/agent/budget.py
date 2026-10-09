"""Budget guard for LLM calls: cache, per-call usage log, spend cap.

- Identical requests (same provider, model, system prompt, history, tools) are served
  from an in-memory cache for CACHE_TTL_S (10 minutes) — no tokens spent.
- Every call (cached or not) is appended to logs/agent_usage.jsonl.
- Estimated spend is summed from the log; calls stop at AGENT_BUDGET_USD.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.agent.llm import LLMClient, LLMResponse, Message

CACHE_TTL_S = 600
DEFAULT_BUDGET_USD = 15.0
USAGE_LOG = Path(__file__).resolve().parents[2] / "logs" / "agent_usage.jsonl"

# USD per 1M tokens (input, output), paid tier, text.
# Source: https://ai.google.dev/gemini-api/docs/pricing (checked 2026-10-05).
PRICES_PER_M: dict[str, tuple[float, float]] = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.8-flash": (0.75, 3.75),
}

_cache: dict[str, tuple[float, LLMResponse]] = {}
_lock = threading.Lock()


class BudgetExceeded(Exception):
    """Estimated spend has reached AGENT_BUDGET_USD."""


def budget_usd() -> float:
    try:
        return float(os.environ.get("AGENT_BUDGET_USD", DEFAULT_BUDGET_USD))
    except ValueError:
        return DEFAULT_BUDGET_USD


def _json_safe(history: list[Message]) -> list[Message]:
    """History without raw signature bytes (they do not change the request meaning)."""
    out = []
    for m in history:
        m = dict(m)
        if "calls" in m:
            m["calls"] = [
                {k: v for k, v in c.items() if k != "signature"} for c in m["calls"]
            ]
        out.append(m)
    return out


def cache_key(
    client: LLMClient, system: str, history: list[Message], tools: list[dict]
) -> str:
    payload = json.dumps(
        [
            client.provider,
            client.model,
            system,
            _json_safe(history),
            [t["name"] for t in tools],
        ],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def estimate_cost(model: str, prompt_tokens: int, output_tokens: int) -> float | None:
    price = PRICES_PER_M.get(model)
    if price is None:
        return None
    return round(prompt_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1], 6)


def _append_log(entry: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def usage_summary(path: Path | None = None) -> dict[str, Any]:
    """Totals from the usage log (what the dev-console counter shows)."""
    path = path or USAGE_LOG
    totals = {
        "calls": 0,
        "cached_calls": 0,
        "prompt_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "unpriced_calls": 0,
    }
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            totals["calls"] += 1
            totals["cached_calls"] += int(bool(e.get("cached")))
            totals["prompt_tokens"] += int(e.get("prompt_tokens") or 0)
            totals["output_tokens"] += int(e.get("output_tokens") or 0)
            if (
                e.get("cost_usd") is None
                and not e.get("cached")
                and e.get("provider") != "ollama"
            ):
                totals["unpriced_calls"] += 1
            totals["estimated_cost_usd"] += float(e.get("cost_usd") or 0.0)
    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"], 4)
    totals["budget_usd"] = budget_usd()
    totals["remaining_usd"] = round(
        totals["budget_usd"] - totals["estimated_cost_usd"], 4
    )
    totals["price_source"] = (
        "https://ai.google.dev/gemini-api/docs/pricing (2026-10-05)"
    )
    return totals


def guarded_generate(
    client: LLMClient,
    system: str,
    history: list[Message],
    tools: list[dict[str, Any]],
    *,
    purpose: str,
    log_path: Path | None = None,
) -> tuple[LLMResponse, bool]:
    """Cached, budget-checked, logged call. Returns (response, served_from_cache)."""
    path = log_path or USAGE_LOG
    key = cache_key(client, system, history, tools)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL_S:
        _append_log(
            {
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "provider": client.provider,
                "model": client.model,
                "purpose": purpose,
                "cached": True,
                "prompt_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            },
            path,
        )
        return hit[1], True
    if client.provider != "ollama":
        spent = usage_summary(path)["estimated_cost_usd"]
        if spent >= budget_usd():
            raise BudgetExceeded(
                f"Estimated AI spend ${spent:.2f} has reached the ${budget_usd():.2f} budget "
                "(AGENT_BUDGET_USD)."
            )
    resp = client.generate(system, history, tools)
    cost = (
        0.0
        if client.provider == "ollama"
        else estimate_cost(client.model, resp.prompt_tokens, resp.output_tokens)
    )
    _append_log(
        {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "provider": client.provider,
            "model": client.model,
            "purpose": purpose,
            "cached": False,
            "prompt_tokens": resp.prompt_tokens,
            "output_tokens": resp.output_tokens,
            "cost_usd": cost,
        },
        path,
    )
    from core import demo  # local import: demo imports this module lazily too

    demo.record_spend(cost)
    with _lock:
        _cache[key] = (now, resp)
    return resp, False


def clear_cache() -> None:
    with _lock:
        _cache.clear()
