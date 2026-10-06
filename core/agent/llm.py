"""LLM providers for the agent: Gemini (google-genai) with an optional local Ollama fallback.

History is provider-neutral (kept server-side, never sent to the browser):
    {"role": "user",  "text": str}
    {"role": "model", "text": str, "calls": [{"id", "name", "args", "signature"}]}
    {"role": "tool",  "results": [{"id", "name", "response": dict}]}
Gemini 3 function calls carry a thought signature that must be sent back on the
next turn; it is kept as raw bytes in "signature".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_OLLAMA_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_S = 120.0

Message = dict[str, Any]


class ProviderUnavailable(Exception):
    """The provider is not configured or cannot be reached."""


@dataclass
class LLMResponse:
    text: str
    calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    output_tokens: int = 0


class LLMClient(Protocol):
    provider: str
    model: str

    def generate(
        self, system: str, history: list[Message], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...


def max_output_tokens() -> int:
    try:
        return int(os.environ.get("AGENT_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS))
    except ValueError:
        return DEFAULT_MAX_OUTPUT_TOKENS


# ------------------------------------------------------------------ Gemini


class GeminiClient:
    provider = "gemini"

    def __init__(self, api_key: str, model: str, sdk_client: Any | None = None) -> None:
        if not model:
            raise ProviderUnavailable("GEMINI_MODEL is not set")
        self.model = model
        if sdk_client is None:
            from google import genai

            sdk_client = genai.Client(api_key=api_key)
        self._client = sdk_client

    @staticmethod
    def to_contents(history: list[Message]) -> list[Any]:
        from google.genai import types

        contents = []
        for m in history:
            if m["role"] == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=m["text"])])
                )
            elif m["role"] == "model":
                parts = [types.Part(text=m["text"])] if m.get("text") else []
                for c in m.get("calls", []):
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                id=c.get("id"), name=c["name"], args=c.get("args") or {}
                            ),
                            thought_signature=c.get("signature"),
                        )
                    )
                contents.append(types.Content(role="model", parts=parts))
            elif m["role"] == "tool":
                parts = [
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=r.get("id"),
                            name=r["name"],
                            response={"result": r["response"]},
                        )
                    )
                    for r in m["results"]
                ]
                contents.append(types.Content(role="user", parts=parts))
        return contents

    def generate(
        self, system: str, history: list[Message], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_output_tokens(),
            temperature=0.2,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t["name"],
                            description=t["description"],
                            parameters_json_schema=t["input_schema"],
                        )
                        for t in tools
                    ]
                )
            ]
            if tools
            else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        try:
            resp = self._client.models.generate_content(
                model=self.model, contents=self.to_contents(history), config=config
            )
        except (errors.APIError, httpx.HTTPError, OSError) as exc:
            raise ProviderUnavailable(f"gemini: {exc}") from exc
        return self.parse(resp)

    @staticmethod
    def parse(resp: Any) -> LLMResponse:
        texts, calls = [], []
        candidates = getattr(resp, "candidates", None) or []
        parts = (
            (candidates[0].content.parts or [])
            if candidates and candidates[0].content
            else []
        )
        for p in parts:
            if getattr(p, "function_call", None):
                fc = p.function_call
                calls.append(
                    {
                        "id": fc.id,
                        "name": fc.name,
                        "args": dict(fc.args or {}),
                        "signature": getattr(p, "thought_signature", None),
                    }
                )
            elif getattr(p, "text", None) and not getattr(p, "thought", False):
                texts.append(p.text)
        usage = getattr(resp, "usage_metadata", None)
        prompt = int(getattr(usage, "prompt_token_count", 0) or 0)
        output = int(getattr(usage, "candidates_token_count", 0) or 0) + int(
            getattr(usage, "thoughts_token_count", 0) or 0
        )
        return LLMResponse("\n".join(texts).strip(), calls, prompt, output)


# ------------------------------------------------------------------ Ollama


class OllamaClient:
    provider = "ollama"

    def __init__(
        self, model: str, base_url: str | None = None, http: httpx.Client | None = None
    ) -> None:
        self.model = model
        self.base_url = (
            base_url or os.environ.get("OLLAMA_URL") or DEFAULT_OLLAMA_URL
        ).rstrip("/")
        self._http = http or httpx.Client(timeout=OLLAMA_TIMEOUT_S)

    @staticmethod
    def to_messages(system: str, history: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in history:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "model":
                msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": m.get("text", ""),
                }
                if m.get("calls"):
                    msg["tool_calls"] = [
                        {
                            "function": {
                                "name": c["name"],
                                "arguments": c.get("args") or {},
                            }
                        }
                        for c in m["calls"]
                    ]
                out.append(msg)
            elif m["role"] == "tool":
                out += [
                    {
                        "role": "tool",
                        "tool_name": r["name"],
                        "content": json.dumps(r["response"], default=str),
                    }
                    for r in m["results"]
                ]
        return out

    def generate(
        self, system: str, history: list[Message], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        body = {
            "model": self.model,
            "messages": self.to_messages(system, history),
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ],
            "stream": False,
            "options": {"num_predict": max_output_tokens(), "temperature": 0.2},
        }
        try:
            resp = self._http.post(f"{self.base_url}/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(f"ollama: {exc}") from exc
        msg = data.get("message") or {}
        calls = [
            {
                "id": f"ollama-{i}",
                "name": c["function"]["name"],
                "args": c["function"].get("arguments") or {},
                "signature": None,
            }
            for i, c in enumerate(msg.get("tool_calls") or [])
        ]
        return LLMResponse(
            (msg.get("content") or "").strip(),
            calls,
            int(data.get("prompt_eval_count") or 0),
            int(data.get("eval_count") or 0),
        )


# ------------------------------------------------------------------ selection


def configured_clients() -> list[LLMClient]:
    """Gemini first (key + model set), then Ollama if OLLAMA_MODEL is set."""
    clients: list[LLMClient] = []
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    if key and model:
        try:
            clients.append(GeminiClient(key, model))
        except (ProviderUnavailable, ImportError):
            pass
    ollama = os.environ.get("OLLAMA_MODEL", "").strip()
    if ollama:
        clients.append(OllamaClient(ollama))
    return clients


def status() -> dict[str, Any]:
    """What the UI needs to enable/disable the briefing and chat (no network calls)."""
    key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    model = os.environ.get("GEMINI_MODEL", "").strip()
    ollama = os.environ.get("OLLAMA_MODEL", "").strip()
    if key and model:
        return {
            "available": True,
            "provider": "gemini",
            "model": model,
            "fallback": "ollama" if ollama else None,
            "reason": None,
        }
    if ollama:
        return {
            "available": True,
            "provider": "ollama",
            "model": ollama,
            "fallback": None,
            "reason": None if key else "No GEMINI_API_KEY; using local Ollama.",
        }
    missing = "GEMINI_API_KEY" if not key else "GEMINI_MODEL"
    return {
        "available": False,
        "provider": None,
        "model": None,
        "fallback": None,
        "reason": f"AI briefing and chat are off: {missing} is not set in .env. "
        "Forecast, map and routing work without it.",
    }
