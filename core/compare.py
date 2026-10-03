"""Compare two risk policies: overlap, movers, reasons."""

from __future__ import annotations

from typing import Any

from core.config import RiskConfig
from core.scoring import score


def compare(
    cfg_a: RiskConfig,
    cfg_b: RiskConfig,
    top: int = 15,
) -> dict[str, Any]:
    """Overlap and movers between two configs' top-N rankings."""
    a = score(cfg_a, top=top)
    b = score(cfg_b, top=top)
    rank_a = {r["corridor"]: r for r in a}
    rank_b = {r["corridor"]: r for r in b}
    set_a = set(rank_a)
    set_b = set(rank_b)

    overlap = sorted(set_a & set_b)
    entered = sorted(set_b - set_a)
    dropped = sorted(set_a - set_b)

    movers: list[dict[str, Any]] = []
    for corridor in sorted(set_a | set_b):
        in_a = corridor in rank_a
        in_b = corridor in rank_b
        if not in_a and not in_b:
            continue
        from_rank = rank_a[corridor]["rank"] if in_a else None
        to_rank = rank_b[corridor]["rank"] if in_b else None
        if from_rank == to_rank and in_a and in_b:
            # still record if score components shifted a lot? HANDOFF wants movers
            # that rose/fell — skip unchanged ranks.
            continue
        if from_rank is None or to_rank is None:
            delta = None
            reason = "entered" if from_rank is None else "dropped"
        else:
            delta = from_rank - to_rank  # positive = rose (better rank)
            ra, rb = rank_a[corridor], rank_b[corridor]
            d_like = abs(rb["likelihood"] - ra["likelihood"])
            d_cons = abs(rb["consequence"] - ra["consequence"])
            reason = "consequence" if d_cons >= d_like else "likelihood"
        movers.append(
            {
                "corridor": corridor,
                "from": from_rank,
                "to": to_rank,
                "delta": delta,
                "reason": reason,
            }
        )

    # Prefer corridors that changed rank magnitude for deliverables.
    movers.sort(
        key=lambda m: (
            0 if m["delta"] is None else -abs(m["delta"]),
            m["corridor"],
        )
    )

    return {
        "overlap": len(overlap),
        "overlap_corridors": overlap,
        "entered": entered,
        "dropped": dropped,
        "movers": movers,
        "top_a": a,
        "top_b": b,
    }
