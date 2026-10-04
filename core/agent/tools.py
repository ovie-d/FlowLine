"""Agent tools — thin wrappers over core. Never invent numbers."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from core.assumptions import get_assumptions
from core.compare import compare as compare_configs
from core.config import RiskConfig
from core.scoring import explain_corridor, score
from core.storage import VALID_ACTIONS, append_decision
from core.triage import draft_triage


def _config_from_overrides(overrides: dict[str, Any] | None) -> RiskConfig:
    cfg = RiskConfig()
    if not overrides:
        return cfg
    allowed = {
        "weights",
        "label",
        "half_life_years",
        "include_facility_events",
        "min_incidents_confident",
        "gas_high_m3",
        "liquid_high_m3",
        "count_only",
    }
    kwargs: dict[str, Any] = {}
    for k, v in overrides.items():
        if k in allowed:
            kwargs[k] = v
        elif k == "high":
            weights = dict(cfg.weights)
            weights["high"] = float(v)
            kwargs["weights"] = weights
        elif k == "medium":
            weights = dict(kwargs.get("weights", cfg.weights))
            weights["medium"] = float(v)
            kwargs["weights"] = weights
        elif k == "low":
            weights = dict(kwargs.get("weights", cfg.weights))
            weights["low"] = float(v)
            kwargs["weights"] = weights
    return replace(cfg, **kwargs) if kwargs else cfg


def _policy_from_config(cfg: RiskConfig) -> dict[str, Any]:
    if cfg.count_only:
        return {"count_only": True}
    return {
        "high": float(cfg.weights["high"]),
        "medium": float(cfg.weights["medium"]),
        "low": float(cfg.weights["low"]),
        "label": cfg.label,
    }


def get_ranking(
    config_overrides: dict[str, Any] | None = None, top: int = 15
) -> list[dict]:
    """Ranked corridors under a given policy."""
    cfg = _config_from_overrides(config_overrides)
    return score(cfg, top=top)


def explain_corridor_tool(
    name: str, config_overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Likelihood vs consequence, incident types, causes, drivers."""
    cfg = _config_from_overrides(config_overrides)
    return explain_corridor(name, cfg)


def compare_tool(
    a: dict[str, Any] | None = None,
    b: dict[str, Any] | None = None,
    top: int = 15,
) -> dict[str, Any]:
    """Overlap + movers with reasons between two configs."""
    cfg_a = _config_from_overrides(a)
    cfg_b = _config_from_overrides(b)
    result = compare_configs(cfg_a, cfg_b, top=top)
    compact_movers = result["movers"][:12]
    return {
        "overlap": result["overlap"],
        "entered": result["entered"],
        "dropped": result["dropped"],
        "movers": compact_movers,
        "top_a": [
            {
                "rank": r["rank"],
                "corridor": r["corridor"],
                "score": r["score"],
                "n": r["n"],
                "n_high": r["n_high"],
            }
            for r in result["top_a"]
        ],
        "top_b": [
            {
                "rank": r["rank"],
                "corridor": r["corridor"],
                "score": r["score"],
                "n": r["n"],
                "n_high": r["n_high"],
            }
            for r in result["top_b"]
        ],
    }


def get_assumptions_tool() -> list[dict[str, Any]]:
    return get_assumptions()


def auto_triage(
    config_overrides: dict[str, Any] | None = None, top: int = 15
) -> dict[str, Any]:
    """Draft escalate/inspect/defer for the top corridors. Does not write the log."""
    cfg = _config_from_overrides(config_overrides)
    return draft_triage(cfg, top=top)


def log_decision(
    corridor: str,
    action: str,
    priority: str,
    reason: str,
    policy: dict[str, Any] | None = None,
    source: str = "planner",
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a planner decision. Only call on explicit user request."""
    action_l = action.strip().lower()
    if action_l not in VALID_ACTIONS:
        return {
            "error": f"action must be one of {sorted(VALID_ACTIONS)}, got {action!r}"
        }
    cfg = _config_from_overrides(config_overrides)
    entry_policy = policy if policy is not None else _policy_from_config(cfg)
    try:
        stored = append_decision(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "corridor": corridor,
                "action": action_l,
                "priority": priority,
                "reason": reason,
                "policy": entry_policy,
                "source": source,
            }
        )
    except ValueError as exc:
        return {"error": str(exc)}
    return {"ok": True, "logged": stored}


TOOL_FUNCTIONS = {
    "get_ranking": get_ranking,
    "explain_corridor": explain_corridor_tool,
    "compare": compare_tool,
    "get_assumptions": get_assumptions_tool,
    "auto_triage": auto_triage,
    "log_decision": log_decision,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_ranking",
        "description": (
            "Return the top ranked pipeline corridors under a risk policy. "
            'Pass config_overrides such as {"high": 6} or {"count_only": true}.'
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_overrides": {
                    "type": "object",
                    "description": "Optional RiskConfig field overrides or {high: number}.",
                },
                "top": {
                    "type": "integer",
                    "description": "How many corridors to return.",
                    "default": 15,
                },
            },
        },
    },
    {
        "name": "explain_corridor",
        "description": (
            "Explain one corridor: likelihood vs consequence, drivers, recent incidents, causes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Corridor name, e.g. Sherwood Park",
                },
                "config_overrides": {"type": "object"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "compare",
        "description": "Compare two risk policies: overlap, entered, dropped, movers with reasons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {
                    "type": "object",
                    "description": "Config overrides for policy A (e.g. count_only).",
                },
                "b": {
                    "type": "object",
                    "description": "Config overrides for policy B (e.g. high=6).",
                },
                "top": {"type": "integer", "default": 15},
            },
        },
    },
    {
        "name": "get_assumptions",
        "description": "List live modeling assumptions with validation status and evidence.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "auto_triage",
        "description": (
            "Draft escalate/inspect/defer actions for the top corridors under a risk policy. "
            "Does not write the decision log. Summarize drafts and ask the planner which to approve."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_overrides": {
                    "type": "object",
                    "description": "Optional RiskConfig overrides or {high: number}.",
                },
                "top": {"type": "integer", "default": 15},
            },
        },
    },
    {
        "name": "log_decision",
        "description": (
            "Record the planner's Monday decision: inspect / escalate / defer. "
            "Only call when the user explicitly asks to log a decision for named corridors."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "corridor": {"type": "string"},
                "action": {"type": "string", "enum": ["inspect", "escalate", "defer"]},
                "priority": {"type": "string", "description": "e.g. P1"},
                "reason": {"type": "string"},
                "policy": {
                    "type": "object",
                    "description": "Optional policy snapshot, e.g. {high: 6}.",
                },
                "source": {
                    "type": "string",
                    "enum": ["planner", "agent_triage"],
                    "default": "planner",
                },
                "config_overrides": {"type": "object"},
            },
            "required": ["corridor", "action", "priority", "reason"],
        },
    },
]


_POLICY_KEYS = frozenset({"high", "medium", "low", "count_only", "weights"})


def _has_own_policy(overrides: dict[str, Any] | None) -> bool:
    if not overrides:
        return False
    return any(k in overrides for k in _POLICY_KEYS)


def _merge_dashboard_policy(
    name: str,
    arguments: dict[str, Any],
    policy: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fill missing tool config from the dashboard policy; never override the model."""
    if not policy:
        return arguments
    args = dict(arguments)

    if name in ("get_ranking", "explain_corridor", "auto_triage"):
        overrides = args.get("config_overrides")
        existing = overrides if isinstance(overrides, dict) else None
        if not _has_own_policy(existing):
            args["config_overrides"] = {**(existing or {}), **policy}

    elif name == "compare":
        side_a = args.get("a")
        existing = side_a if isinstance(side_a, dict) else None
        if not _has_own_policy(existing):
            args["a"] = {**(existing or {}), **policy}

    elif name == "log_decision":
        if args.get("policy") is None:
            args["policy"] = dict(policy)
        overrides = args.get("config_overrides")
        existing = overrides if isinstance(overrides, dict) else None
        if not _has_own_policy(existing):
            args["config_overrides"] = {**(existing or {}), **policy}

    return args


def dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> Any:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    merged = _merge_dashboard_policy(name, arguments, policy)
    return fn(**merged)
