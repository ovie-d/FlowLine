"""Corridor risk scoring — sole source of truth for ranking math."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from core.config import RiskConfig
from core.data import load_incidents
from core.labels import LOW_CONFIDENCE_LABEL


def _to_jsonable(value: Any) -> Any:
    if value is None or (
        isinstance(value, float) and (math.isnan(value) or math.isinf(value))
    ):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        converted = value.item()
        if isinstance(converted, float) and (
            math.isnan(converted) or math.isinf(converted)
        ):
            return None
        return converted
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _round2(x: float) -> float:
    return round(float(x), 2)


def _decay_factor(age_years: float, half_life: float | None) -> float:
    if half_life is None:
        return 1.0
    return 0.5 ** (float(age_years) / float(half_life))


def _incident_weight(row: pd.Series, config: RiskConfig) -> float:
    if config.count_only:
        return 1.0
    col = "severity_v2" if config.label == "v2" else "severity_lab"
    label = str(row[col])
    return float(config.weights.get(label, 1.0))


def _driver_dict(row: pd.Series, weight: float) -> dict[str, Any]:
    return {
        "date": _to_jsonable(row["date"]),
        "type": _to_jsonable(row["incident_type"]),
        "substance": _to_jsonable(row["substance"]),
        "weight": _round2(weight),
    }


def score(config: RiskConfig | None = None, top: int = 15) -> list[dict[str, Any]]:
    """Rank corridors under ``config``. Returns JSON-serializable rows."""
    cfg = config or RiskConfig()
    df, _report = load_incidents(cfg)
    if df.empty:
        return []

    rows: list[dict[str, Any]] = []
    for corridor, group in df.groupby("corridor", sort=True):
        contributions: list[tuple[float, int, dict[str, Any]]] = []
        weight_sum = 0.0
        decay_sum = 0.0
        n_high = n_medium = n_low = 0
        sev_col = "severity_v2" if cfg.label == "v2" else "severity_lab"

        for i, (_, row) in enumerate(group.iterrows()):
            w = _incident_weight(row, cfg)
            decay = _decay_factor(float(row["age_years"]), cfg.half_life_years)
            contrib = w * decay
            weight_sum += contrib
            decay_sum += decay
            label = str(row[sev_col])
            if label == "high":
                n_high += 1
            elif label == "medium":
                n_medium += 1
            else:
                n_low += 1
            contributions.append((contrib, i, _driver_dict(row, contrib)))

        n = len(group)
        likelihood = float(decay_sum) if not cfg.count_only else float(n)
        if cfg.count_only:
            consequence = 1.0
            total_score = float(n)
        else:
            consequence = weight_sum / decay_sum if decay_sum else 0.0
            total_score = weight_sum

        contributions.sort(key=lambda t: (-t[0], t[1]))
        drivers = [d for _, _, d in contributions[:3]]

        operator = group["company"].value_counts().index[0]
        last_incident = group["date"].max()
        lat = float(group["latitude"].mean())
        lon = float(group["longitude"].mean())
        confidence = "ok" if n >= cfg.min_incidents_confident else "low"

        rows.append(
            {
                "corridor": str(corridor),
                "score": total_score,
                "likelihood": likelihood,
                "consequence": consequence,
                "n": n,
                "n_high": n_high,
                "n_medium": n_medium,
                "n_low": n_low,
                "confidence": confidence,
                "drivers": drivers,
                "operator": str(operator),
                "lat": lat,
                "lon": lon,
                "last_incident": last_incident,
            }
        )

    rows.sort(
        key=lambda r: (
            -r["score"],
            -r["n_high"],
            -pd.Timestamp(r["last_incident"]).timestamp(),
            r["corridor"],
        )
    )

    out: list[dict[str, Any]] = []
    for rank, row in enumerate(rows[:top], start=1):
        out.append(
            {
                "rank": rank,
                "corridor": row["corridor"],
                "score": _round2(row["score"]),
                "likelihood": _round2(row["likelihood"]),
                "consequence": _round2(row["consequence"]),
                "n": row["n"],
                "n_high": row["n_high"],
                "n_medium": row["n_medium"],
                "n_low": row["n_low"],
                "confidence": row["confidence"],
                "drivers": row["drivers"],
                "operator": row["operator"],
                "lat": _round2(row["lat"]),
                "lon": _round2(row["lon"]),
                "last_incident": _to_jsonable(row["last_incident"]),
            }
        )
    return out


def explain_corridor(name: str, config: RiskConfig | None = None) -> dict[str, Any]:
    """Corridor detail for the agent. Unknown name -> {error}."""
    cfg = config or RiskConfig()
    ranked = score(cfg, top=10_000)
    match = next((r for r in ranked if r["corridor"].lower() == name.lower()), None)
    if match is None:
        return {"error": f"Unknown corridor: {name}"}

    df, _ = load_incidents(cfg)
    group = df[df["corridor"].str.lower() == name.lower()]
    incidents = []
    for _, row in group.sort_values("date", ascending=False).head(12).iterrows():
        sev_col = "severity_v2" if cfg.label == "v2" else "severity_lab"
        incidents.append(
            {
                "date": _to_jsonable(row["date"]),
                "type": _to_jsonable(row["incident_type"]),
                "substance": _to_jsonable(row["substance"]),
                "cause": _to_jsonable(row["cause"]),
                "severity": _to_jsonable(row[sev_col]),
                "release_m3": _to_jsonable(row["release_m3"]),
            }
        )
    return {
        **match,
        "confidence_label": (
            LOW_CONFIDENCE_LABEL if match["confidence"] == "low" else None
        ),
        "incidents": incidents,
        "causes": (
            group["cause"].value_counts().head(8).astype(int).to_dict()
            if len(group)
            else {}
        ),
    }
