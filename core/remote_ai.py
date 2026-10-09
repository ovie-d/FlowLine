"""AI briefing/chat for local installs without a Gemini key, via the online demo.

When FLOWLINE_REMOTE_AI is set (e.g. https://<space>.hf.space/api) and no local AI key is
configured, /briefing and /agent are forwarded to the online demo, which applies the
same per-visitor daily limit. The key stays on the demo server; nothing is stored here.
A local GEMINI_API_KEY always takes precedence.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from core import demo

TIMEOUT_S = 60.0
STATUS_TIMEOUT_S = 6.0


def url() -> str:
    return os.environ.get("FLOWLINE_REMOTE_AI", "").strip().rstrip("/")


def _headers() -> dict[str, str]:
    v = demo.raw_visitor()
    return {"X-Flowline-Visitor": v} if v else {}


def status() -> dict[str, Any] | None:
    """The demo's AI status for this visitor, or None if it can't be reached."""
    if not url():
        return None
    try:
        resp = httpx.get(
            f"{url()}/agent/status", headers=_headers(), timeout=STATUS_TIMEOUT_S
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError):
        return None


def forward(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST to the online demo; a failure comes back as a normal 'unavailable' answer."""
    try:
        resp = httpx.post(
            f"{url()}{path}", json=payload, headers=_headers(), timeout=TIMEOUT_S
        )
        resp.raise_for_status()
        out = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "answer": "",
            "error": True,
            "reason": f"The online demo's AI could not be reached ({exc.__class__.__name__}).",
        }
    out["via_online_demo"] = True
    return out
