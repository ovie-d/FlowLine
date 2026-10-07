"""Compare two risk policies: overlap, movers, reasons."""

from __future__ import annotations

from typing import Any

from core.config import RiskConfig
from core.data import load_incidents
from core.scoring import score

# Label-independent yardstick for the improvement round (not our severity labels).
SERIOUS_INCIDENT_TYPES: frozenset[str] = frozenset(
    {
        "Adverse Environmental Effects",
        "Explosion",
        "Fatality",
        "Release of Substance",
        "Serious Injury (as defined in the OPR)",
    }
)

_DEFAULT_WEIGHTS: dict[str, float] = {"high": 3.0, "medium": 1.5, "low": 1.0}


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
            # still record if score components shifted a lot? The v1 handoff wants movers
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


def _stage_metrics(
    *,
    stage: str,
    ranked: list[dict[str, Any]],
    df,
    serious_total: int,
    baseline_names: set[str],
) -> dict[str, Any]:
    names = [r["corridor"] for r in ranked]
    name_set = set(names)
    subset = df[df["corridor"].isin(name_set)]
    serious_captured = int(subset["incident_type"].isin(SERIOUS_INCIDENT_TYPES).sum())
    incidents_covered = len(subset)
    overlap = len(name_set & baseline_names) if baseline_names else len(name_set)
    return {
        "stage": stage,
        "serious_captured": serious_captured,
        "serious_total": serious_total,
        "incidents_covered": incidents_covered,
        "top5": names[:5],
        "overlap_vs_baseline": overlap,
    }


def _policy_snapshot(cfg: RiskConfig) -> dict[str, Any]:
    if cfg.count_only:
        return {
            "high": 1.0,
            "medium": float(cfg.weights.get("medium", 1.5)),
            "low": float(cfg.weights.get("low", 1.0)),
            "count_only": True,
        }
    return {
        "high": float(cfg.weights["high"]),
        "medium": float(cfg.weights["medium"]),
        "low": float(cfg.weights["low"]),
        "count_only": False,
    }


def improvement_for(cfg: RiskConfig, top: int = 15) -> dict[str, Any]:
    """Serious-event + incident coverage for ``cfg`` vs count-only baseline.

    Same label-independent yardstick as ``improvement_round`` (incident types,
    not severity labels). Baseline is always count-only.
    """
    df, _report = load_incidents()
    serious_total = int(df["incident_type"].isin(SERIOUS_INCIDENT_TYPES).sum())

    cfg_baseline = RiskConfig(count_only=True, weights=dict(_DEFAULT_WEIGHTS))
    ranked_current = score(cfg, top=top)
    ranked_baseline = score(cfg_baseline, top=top)

    current_names = {r["corridor"] for r in ranked_current}
    baseline_names = {r["corridor"] for r in ranked_baseline}

    current_subset = df[df["corridor"].isin(current_names)]
    baseline_subset = df[df["corridor"].isin(baseline_names)]

    return {
        "policy": _policy_snapshot(cfg),
        "serious_total": serious_total,
        "current": {
            "serious_captured": int(
                current_subset["incident_type"].isin(SERIOUS_INCIDENT_TYPES).sum()
            ),
            "incidents_covered": len(current_subset),
        },
        "baseline": {
            "serious_captured": int(
                baseline_subset["incident_type"].isin(SERIOUS_INCIDENT_TYPES).sum()
            ),
            "incidents_covered": len(baseline_subset),
        },
    }


def improvement_round(top: int = 15) -> dict[str, Any]:
    """First result vs improved result under a label-independent yardstick.

    Stages (same weights): count-only baseline → lab labels → our severity_v2.
    ``ours_heavy`` is a sibling row linking to the high=6 slider flip.
    """
    weights = dict(_DEFAULT_WEIGHTS)
    df, _report = load_incidents()
    serious_total = int(df["incident_type"].isin(SERIOUS_INCIDENT_TYPES).sum())

    cfg_baseline = RiskConfig(count_only=True, weights=weights)
    cfg_lab = RiskConfig(label="lab", weights=weights)
    cfg_ours = RiskConfig(label="v2", weights=weights)
    cfg_heavy = RiskConfig(
        label="v2",
        weights={"high": 6.0, "medium": 1.5, "low": 1.0},
    )

    ranked_baseline = score(cfg_baseline, top=top)
    ranked_lab = score(cfg_lab, top=top)
    ranked_ours = score(cfg_ours, top=top)
    ranked_heavy = score(cfg_heavy, top=top)

    baseline_names = {r["corridor"] for r in ranked_baseline}

    baseline = _stage_metrics(
        stage="baseline",
        ranked=ranked_baseline,
        df=df,
        serious_total=serious_total,
        baseline_names=baseline_names,
    )
    lab = _stage_metrics(
        stage="lab",
        ranked=ranked_lab,
        df=df,
        serious_total=serious_total,
        baseline_names=baseline_names,
    )
    ours = _stage_metrics(
        stage="ours",
        ranked=ranked_ours,
        df=df,
        serious_total=serious_total,
        baseline_names=baseline_names,
    )
    ours_heavy = _stage_metrics(
        stage="ours_heavy",
        ranked=ranked_heavy,
        df=df,
        serious_total=serious_total,
        baseline_names=baseline_names,
    )

    summary = (
        f"Baseline captured {baseline['serious_captured']}/{serious_total} "
        f"serious events; ours captures {ours['serious_captured']}/{serious_total} "
        f"while covering fewer incidents."
    )

    return {
        "weights": weights,
        "stages": [baseline, lab, ours],
        "ours_heavy": ours_heavy,
        "summary": summary,
    }
