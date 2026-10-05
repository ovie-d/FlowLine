"""Hazard-mix forecast for a location and date (the deployed model, no weather).

Context for a point that is not an incident:
- province: from the nearest recorded incident (no boundary layer is bundled)
- operator group / commodity: from the nearest CER pipeline system
- distance to that system, day of year, and area history (strictly before the date)

Trust rules (docs/MODEL_REPORT.md):
- low_evidence when fewer than LOW_EVIDENCE_PRIOR prior incidents lie within 25 km
- probabilities above LOWER_CERTAINTY_ABOVE are displayed as ">50%, lower certainty"
  (the model is overconfident there on the test set)
"""

from __future__ import annotations

import calendar
import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg

from core.features import AREA_RADIUS_KM, History, feature_row
from core.model import HazardModel
from core.operators import OPERATOR_ALIASES, OTHER_OPERATOR
from core.taxonomy import HAZARD_LABELS, LOW_EVIDENCE_GROUPS, MODEL_TARGETS

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hazard_forecast"
EVAL_SUMMARY_PATH = MODEL_PATH.with_suffix(".eval.json")
LOW_EVIDENCE_PRIOR = 3
LOWER_CERTAINTY_ABOVE = 0.5
DRIVERS_PER_HAZARD = 3
TOP_HAZARDS_WITH_DRIVERS = 3
DISCLAIMER = (
    "Forecasts are based on historical public incident data. Flowline supports "
    "engineering judgment; it does not certify any pipe as safe."
)

# Systems-layer company -> operator group (reverse of OPERATOR_ALIASES).
LAYER_TO_GROUP: dict[str, str] = {
    layer: group for group, layer in OPERATOR_ALIASES.values() if layer is not None
}

HISTORY_SQL = """
SELECT event_date, closed_date, latitude, longitude, site_id, hazard_group
FROM incidents ORDER BY event_date, incident_number
"""


@lru_cache(maxsize=1)
def load_model() -> HazardModel:
    return HazardModel.load(MODEL_PATH)


_history_cache: dict[str, History] = {}


def history(conn: psycopg.Connection) -> History:
    """All incidents as a History, cached until the incidents table changes."""
    stamp = conn.execute(
        "SELECT count(*) AS n, max(loaded_at) AS ts FROM incidents"
    ).fetchone()
    key = f"{stamp['n']}:{stamp['ts']}"
    if key not in _history_cache:
        frame = pd.DataFrame(conn.execute(HISTORY_SQL).fetchall())
        if frame.empty:
            frame = pd.DataFrame(
                columns=[
                    "event_date",
                    "closed_date",
                    "latitude",
                    "longitude",
                    "site_id",
                    "hazard_group",
                ]
            )
        _history_cache.clear()
        _history_cache[key] = History.from_frame(frame)
    return _history_cache[key]


POINT = "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography"


def resolve_context(
    conn: psycopg.Connection, lat: float, lon: float, when: date
) -> dict[str, Any]:
    """Province, operator group, commodity and nearest pipeline system for a point.

    Operator / commodity default to the most common operator among earlier incidents
    within AREA_RADIUS_KM (the same encoding the model was trained on); with no nearby
    history they come from the nearest CER pipeline system.
    """
    params = {"lat": lat, "lon": lon, "when": when, "radius_m": AREA_RADIUS_KM * 1000}
    inc = conn.execute(
        f"SELECT province, ST_Distance(geom, {POINT}) / 1000.0 AS km FROM incidents "
        f"ORDER BY geom <-> {POINT} LIMIT 1",
        params,
    ).fetchone()
    pipe = conn.execute(
        f"SELECT pipeline_name, company, commodity, ST_Distance(geom, {POINT}) / 1000.0 AS km "
        f"FROM pipelines ORDER BY geom <-> {POINT} LIMIT 1",
        params,
    ).fetchone()
    nearby = conn.execute(
        "SELECT operator_group, mode() WITHIN GROUP (ORDER BY commodity) AS commodity, "
        "count(*) AS n FROM incidents "
        f"WHERE event_date < %(when)s AND ST_DWithin(geom, {POINT}, %(radius_m)s) "
        "GROUP BY operator_group ORDER BY n DESC, operator_group",
        params,
    ).fetchall()
    systems = conn.execute(
        "SELECT DISTINCT company, commodity FROM pipelines "
        f"WHERE ST_DWithin(geom, {POINT}, %(radius_m)s)",
        params,
    ).fetchall()
    options = {r["operator_group"]: r["commodity"] for r in nearby}
    for sys in systems:
        options.setdefault(
            LAYER_TO_GROUP.get(sys["company"], OTHER_OPERATOR), sys["commodity"]
        )
    if nearby:
        group, commodity, source = (
            nearby[0]["operator_group"],
            nearby[0]["commodity"],
            (
                f"most common operator among {nearby[0]['n']} earlier incidents within "
                f"{AREA_RADIUS_KM:.0f} km"
            ),
        )
    elif pipe:
        group = LAYER_TO_GROUP.get(pipe["company"], OTHER_OPERATOR)
        commodity, source = pipe["commodity"], "nearest mapped CER pipeline system"
        options.setdefault(group, commodity)
    else:
        group, commodity, source = None, None, "unknown"
    return {
        "province": inc["province"] if inc else None,
        "province_source_km": round(float(inc["km"]), 1) if inc else None,
        "nearest_system": pipe["pipeline_name"] if pipe else None,
        "nearest_system_km": round(float(pipe["km"]), 1) if pipe else None,
        "operator_group": group,
        "commodity": commodity,
        "operator_source": source,
        "operator_options": [
            {"operator_group": g, "commodity": c} for g, c in options.items()
        ],
    }


def corridor_location(
    conn: psycopg.Connection, name: str
) -> tuple[float, float] | None:
    row = conn.execute(
        "SELECT latitude, longitude FROM corridors WHERE lower(name) = lower(%s)",
        (name,),
    ).fetchone()
    return (float(row["latitude"]), float(row["longitude"])) if row else None


def alberta_shares(conn: psycopg.Connection) -> dict[str, float]:
    """Historical share of each hazard among Alberta forecast-target incidents."""
    rows = conn.execute(
        "SELECT hazard_group, count(*) AS n FROM incidents "
        "WHERE is_alberta AND is_model_target GROUP BY hazard_group"
    ).fetchall()
    counts = {r["hazard_group"]: int(r["n"]) for r in rows}
    total = sum(counts.values())
    return {c: counts.get(c, 0) / total if total else math.nan for c in MODEL_TARGETS}


def display_probability(p: float) -> dict[str, Any]:
    if p > LOWER_CERTAINTY_ABOVE:
        return {"display": ">50%, lower certainty", "lower_certainty": True}
    return {"display": f"{round(p * 100)}%", "lower_certainty": False}


# ------------------------------------------------------------------ drivers

_MIX_PREFIX = "ah_mix_"
_GROUPED = {
    "latitude": "location",
    "longitude": "location",
    "doy_sin": "season",
    "doy_cos": "season",
}


def _is_missing(v: object) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _count(n: object, singular: str, plural: str) -> str:
    k = int(n)  # type: ignore[arg-type]
    return f"{k} {singular if k == 1 else plural}"


def _describe(feature: str, row: dict[str, Any], when: date) -> str:
    v = row.get(feature)
    if feature == "no_known_history":
        return "No earlier nearby incidents with a known cause"
    if feature == "location":
        return f"Location ({row['latitude']:.2f}, {row['longitude']:.2f})"
    if feature == "season":
        return f"Time of year ({calendar.month_name[when.month]})"
    if feature.startswith(_MIX_PREFIX):
        label = HAZARD_LABELS[feature[len(_MIX_PREFIX) :]]
        return f"{v:.0%} of earlier nearby incidents (each site counted once) were {label.lower()}"
    missing = _is_missing(v)
    r = f"{AREA_RADIUS_KM:.0f} km"
    texts = {
        "operator_group": lambda: f"Operator system: {v}",
        "commodity": lambda: f"Commodity carried: {v}",
        "province": lambda: f"Province: {v}",
        "dist_pipeline_km": lambda: (
            "Distance to mapped pipeline unknown"
            if missing
            else f"{v:.0f} km from the nearest mapped CER pipeline"
        ),
        "ah_n_prior": lambda: (
            f"{_count(v, 'earlier incident', 'earlier incidents')} within {r}"
        ),
        "ah_n_sites": lambda: (
            f"{_count(v, 'distinct earlier site', 'distinct earlier sites')} within {r}"
        ),
        "ah_n_known": lambda: _count(
            v,
            "nearby earlier incident with a known cause",
            "nearby earlier incidents with a known cause",
        ),
        "ah_n_known_sites": lambda: _count(
            v, "nearby site with a known cause", "nearby sites with a known cause"
        ),
        "ah_same_site_n": lambda: (
            f"{_count(v, 'earlier incident', 'earlier incidents')} at this site (within 1 km)"
        ),
        "ah_days_since_last": lambda: (
            "No earlier incident nearby"
            if missing
            else f"Last nearby incident {_count(v, 'day', 'days')} earlier"
        ),
    }
    return texts[feature]() if feature in texts else feature


def drivers_for(
    shap_row: np.ndarray, columns: list[str], row: dict[str, Any], when: date
) -> list[dict[str, Any]]:
    """Top contributions to one class, with location/season components merged."""
    merged: dict[str, float] = {}
    for col, val in zip(columns, shap_row, strict=True):
        key = _GROUPED.get(col, col)
        if col.startswith(_MIX_PREFIX) and _is_missing(row.get(col)):
            key = "no_known_history"
        merged[key] = merged.get(key, 0.0) + float(val)
    top = sorted(merged.items(), key=lambda kv: -abs(kv[1]))[:DRIVERS_PER_HAZARD]
    return [
        {
            "feature": f,
            "text": _describe(f, row, when),
            "effect": "raises" if v > 0 else "lowers",
            "weight": round(v, 3),
        }
        for f, v in top
    ]


# ------------------------------------------------------------------ forecast


def forecast(
    conn: psycopg.Connection,
    *,
    lat: float,
    lon: float,
    when: date,
    operator_group: str | None = None,
) -> dict[str, Any]:
    model = load_model()
    ctx = resolve_context(conn, lat, lon, when)
    if operator_group:
        chosen = {o["operator_group"]: o["commodity"] for o in ctx["operator_options"]}
        ctx["operator_group"] = operator_group
        ctx["commodity"] = chosen.get(operator_group, ctx["commodity"])
        ctx["operator_source"] = "chosen by user"
    row = feature_row(
        history(conn),
        lat=lat,
        lon=lon,
        when=when,
        province=ctx["province"],
        operator_group=ctx["operator_group"],
        commodity=ctx["commodity"],
        dist_pipeline_km=ctx["nearest_system_km"],
        weather=None,
    )
    X = pd.DataFrame([row])
    proba = model.predict_proba(X)[0]
    shap = model.shap_values(X)[0, :, :-1]
    ab = alberta_shares(conn)
    order = np.argsort(-proba)
    hazards = []
    for rank, k in enumerate(order):
        cls = MODEL_TARGETS[k]
        share = ab.get(cls, math.nan)
        hazards.append(
            {
                "hazard_group": cls,
                "label": HAZARD_LABELS[cls],
                "probability": round(float(proba[k]), 4),
                **display_probability(float(proba[k])),
                "alberta_share": None if math.isnan(share) else round(share, 4),
                "vs_alberta": None if not share else round(float(proba[k]) / share, 1),
                "low_evidence_group": cls in LOW_EVIDENCE_GROUPS,
                "drivers": drivers_for(shap[k], model.columns, row, when)
                if rank < TOP_HAZARDS_WITH_DRIVERS
                else [],
            }
        )
    n_prior = int(row["ah_n_prior"])
    return {
        "location": {"latitude": lat, "longitude": lon},
        "date": when.isoformat(),
        "context": ctx,
        "hazards": hazards,
        "evidence": {
            "radius_km": AREA_RADIUS_KM,
            "prior_incidents": n_prior,
            "prior_sites": int(row["ah_n_sites"]),
            "prior_with_known_cause": int(row["ah_n_known"]),
            "same_site_incidents": int(row["ah_same_site_n"]),
        },
        "low_evidence": n_prior < LOW_EVIDENCE_PRIOR,
        "low_evidence_rule": f"fewer than {LOW_EVIDENCE_PRIOR} prior incidents within "
        f"{AREA_RADIUS_KM:.0f} km",
        "weather_in_model": False,
        "model": {
            k: model.meta.get(k) for k in ("trained_through", "trained_at", "rounds")
        },
        "disclaimer": DISCLAIMER,
    }


def model_info() -> dict[str, Any]:
    """Evaluation summary written by scripts/evaluate.py (all numbers from that run)."""
    if not EVAL_SUMMARY_PATH.exists():
        return {"error": "No evaluation summary — run python -m scripts.evaluate"}
    summary = json.loads(EVAL_SUMMARY_PATH.read_text(encoding="utf-8"))
    ca = summary["canada"]["delta_log_loss_vs_best_baseline"]
    ab = summary["alberta"]["delta_log_loss_vs_best_baseline"]

    def gain(d: list[float]) -> str:
        return f"log loss {d[0]:+.3f} (95% CI {d[1]:+.3f} to {d[2]:+.3f})"

    summary["plain_words"] = {
        "canada": (
            f"Beats the best simple baseline on held-out 2022+ incidents: {gain(ca)}."
            if summary["canada"]["beats_best_baseline"]
            else f"Does not beat the best simple baseline on held-out 2022+ incidents: {gain(ca)}."
        ),
        "alberta": (
            f"Beats the best simple baseline in Alberta, but the gain is narrow: {gain(ab)}"
            + (f", {ab[0] / ca[0]:.0%} of the national gain." if ca[0] < 0 else ".")
            if summary["alberta"]["beats_best_baseline"]
            else f"Not distinguishable from the best simple baseline in Alberta: {gain(ab)}."
        ),
        "weather": "Weather is not a model input: it made no measurable difference.",
        "calibration": "Probabilities above 50% were overconfident on the test set; they "
        "are shown as '>50%, lower certainty'.",
    }
    summary["disclaimer"] = DISCLAIMER
    return summary
