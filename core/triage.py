"""Rule-based draft triage over ranked corridors (decision out, not chat)."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from core.config import RiskConfig
from core.data import load_incidents
from core.labels import LOW_CONFIDENCE_LABEL
from core.scoring import score

# Escalate when this many high-consequence incidents and confidence is ok.
# Module constant on purpose — not a RiskConfig field (no API change).
ESCALATE_MIN_HIGH = 3

TYPE_DISPLAY: dict[str, str] = {
    "Adverse Environmental Effects": "environmental effects",
    "Explosion": "explosions",
    "Fatality": "fatalities",
    "Fire": "fires",
    "Operation Beyond Design Limits": "limit breaches",
    "Release of Substance": "releases",
    "Serious Injury (as defined in the OPR)": "serious injuries",
}

BANNED_REASON_SNIPPETS = (
    "n_high=",
    "confidence=",
    "threshold",
    "under current policy",
)


def _policy_snapshot(config: RiskConfig) -> dict[str, Any]:
    if config.count_only:
        return {"count_only": True}
    return {
        "high": float(config.weights["high"]),
        "medium": float(config.weights["medium"]),
        "low": float(config.weights["low"]),
        "label": config.label,
    }


def _type_counts_by_corridor(df: pd.DataFrame) -> dict[str, Counter[str]]:
    out: dict[str, Counter[str]] = {}
    for corridor, group in df.groupby("corridor", sort=True):
        out[str(corridor)] = Counter(group["incident_type"].tolist())
    return out


def _format_types(counts: Counter[str], top: int = 2) -> str:
    if not counts:
        return "none recorded"
    # Count desc, then readable name asc for ties.
    ranked = sorted(
        counts.items(),
        key=lambda kv: (-kv[1], TYPE_DISPLAY.get(kv[0], kv[0].lower())),
    )
    # Always ", " (space after comma) — this string is shown on screen.
    return ", ".join(
        f"{TYPE_DISPLAY.get(raw, raw.lower())} ({n})" for raw, n in ranked[:top]
    )


def _plain_reason(
    *,
    rule: str,
    n: int,
    n_high: int,
    type_counts: Counter[str],
) -> str:
    types = _format_types(type_counts)
    if rule == "R1":
        return f"{n_high} of {n} incidents high-consequence; most common: {types}"
    if rule == "R2":
        return f"{LOW_CONFIDENCE_LABEL}: {n} incidents, {n_high} high-consequence"
    if rule == "R3":
        share = (n_high / n) if n else 0.0
        only = "" if share >= 0.25 else "only "
        return f"{n} incidents, {only}{n_high} high-consequence; most common: {types}"
    return f"{n} incidents, none high-consequence; monitor. Most common: {types}"


def _draft_for_row(row: dict[str, Any], type_counts: Counter[str]) -> dict[str, Any]:
    n_high = int(row["n_high"])
    confidence = str(row["confidence"])
    rank = int(row["rank"])
    n = int(row["n"])

    if n_high >= ESCALATE_MIN_HIGH and confidence == "ok":
        action, priority, rule = "escalate", "P1", "R1"
    elif confidence == "low" and n_high >= 1:
        action, priority, rule = "inspect", "P3", "R2"
    elif n_high >= 1 or rank <= 5:
        action, priority, rule = "inspect", "P2", "R3"
    else:
        action, priority, rule = "defer", "P3", "R4"

    reason = _plain_reason(rule=rule, n=n, n_high=n_high, type_counts=type_counts)
    return {
        "rank": rank,
        "corridor": row["corridor"],
        "action": action,
        "priority": priority,
        "rule": rule,
        "reason": reason,
        "n": n,
        "n_high": n_high,
        "confidence": confidence,
    }


def draft_triage(config: RiskConfig | None = None, top: int = 15) -> dict[str, Any]:
    """Draft inspect/escalate/defer for the top-N corridors. Never writes storage."""
    cfg = config or RiskConfig()
    ranked = score(cfg, top=top)
    df, _report = load_incidents(cfg)
    type_map = _type_counts_by_corridor(df)
    drafts = [
        _draft_for_row(row, type_map.get(row["corridor"], Counter())) for row in ranked
    ]
    counts = {"escalate": 0, "inspect": 0, "defer": 0}
    for d in drafts:
        counts[d["action"]] = counts.get(d["action"], 0) + 1
    return {
        "policy": _policy_snapshot(cfg),
        "drafts": drafts,
        "counts": counts,
    }
