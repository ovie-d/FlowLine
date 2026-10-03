"""Rule-based draft triage over ranked corridors (decision out, not chat)."""

from __future__ import annotations

from typing import Any

from core.config import RiskConfig
from core.scoring import score

# Escalate when this many high-consequence incidents and confidence is ok.
# Module constant on purpose — not a RiskConfig field (no API change).
ESCALATE_MIN_HIGH = 3


def _policy_snapshot(config: RiskConfig) -> dict[str, Any]:
    if config.count_only:
        return {"count_only": True}
    return {
        "high": float(config.weights["high"]),
        "medium": float(config.weights["medium"]),
        "low": float(config.weights["low"]),
        "label": config.label,
    }


def _draft_for_row(row: dict[str, Any]) -> dict[str, Any]:
    n_high = int(row["n_high"])
    confidence = str(row["confidence"])
    rank = int(row["rank"])
    n = int(row["n"])

    if n_high >= ESCALATE_MIN_HIGH and confidence == "ok":
        action, priority, rule = "escalate", "P1", "R1"
        reason = (
            f"{n_high} high-consequence incidents with confidence=ok "
            f"(threshold {ESCALATE_MIN_HIGH})"
        )
    elif confidence == "low" and n_high >= 1:
        action, priority, rule = "inspect", "P3", "R2"
        reason = "thin data: low confidence with at least one high-consequence incident"
    elif n_high >= 1 or rank <= 5:
        action, priority, rule = "inspect", "P2", "R3"
        reason = (
            f"rank {rank} with n_high={n_high}; inspect under current policy"
            if n_high >= 1
            else f"top-5 corridor (rank {rank}) under current policy"
        )
    else:
        action, priority, rule = "defer", "P3", "R4"
        reason = "monitor; minor-only history under current policy"

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
    drafts = [_draft_for_row(row) for row in ranked]
    counts = {"escalate": 0, "inspect": 0, "defer": 0}
    for d in drafts:
        counts[d["action"]] = counts.get(d["action"], 0) + 1
    return {
        "policy": _policy_snapshot(cfg),
        "drafts": drafts,
        "counts": counts,
    }
