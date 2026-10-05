"""Hazard-forecast agent tools — thin, compact wrappers over core. Never invent numbers."""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg

from core.crews import CrewMapError, dispatch, get_crews
from core.forecast import alberta_today, corridor_location, forecast, model_info
from core.insights import washout_insight
from core.pg import try_connect
from core.readiness import readiness
from core.similar import find_similar, similar_to_incident
from core.taxonomy import HAZARD_LABELS, MODEL_TARGETS

NO_DB = {
    "error": "Database unavailable — the forecast tools need `docker compose up -d db`."
}


def _date(value: str | None) -> date:
    return date.fromisoformat(value) if value else alberta_today()


def _point(
    conn: psycopg.Connection,
    latitude: float | None,
    longitude: float | None,
    corridor: str | None,
) -> tuple[float, float] | dict[str, str]:
    if latitude is not None and longitude is not None:
        return float(latitude), float(longitude)
    if corridor:
        loc = corridor_location(conn, corridor)
        return loc if loc else {"error": f"Unknown corridor {corridor!r}"}
    return {"error": "Give latitude and longitude, or a corridor name."}


def _compact_hazard(h: dict[str, Any]) -> dict[str, Any]:
    return {
        "hazard_group": h["hazard_group"],
        "label": h["label"],
        "probability": h["probability"],
        "display": h["display"],
        "alberta_share": h["alberta_share"],
        "vs_alberta": h["vs_alberta"],
        "low_evidence_group": h["low_evidence_group"],
        "drivers": [f"{d['effect']}: {d['text']}" for d in h["drivers"]],
    }


def _compact_forecast(fc: dict[str, Any]) -> dict[str, Any]:
    ctx = fc["context"]
    return {
        "date": fc["date"],
        "location": fc["location"],
        "context": {
            k: ctx[k]
            for k in (
                "province",
                "operator_group",
                "commodity",
                "operator_source",
                "nearest_system",
            )
        },
        "hazards": [_compact_hazard(h) for h in fc["hazards"]],
        "evidence": fc["evidence"],
        "low_evidence": fc["low_evidence"],
        "low_evidence_rule": fc["low_evidence_rule"],
        "disclaimer": fc["disclaimer"],
    }


def _with_conn(fn):
    def wrapper(**kwargs: Any) -> Any:
        conn = try_connect()
        if conn is None:
            return NO_DB
        try:
            with conn:
                return fn(conn, **kwargs)
        except (ValueError, CrewMapError) as exc:
            return {"error": str(exc)}

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


@_with_conn
def get_forecast(
    conn,
    latitude=None,
    longitude=None,
    corridor=None,
    date=None,
    operator_group=None,
) -> dict[str, Any]:
    """Hazard-mix forecast for a point or corridor on a date."""
    where = _point(conn, latitude, longitude, corridor)
    if isinstance(where, dict):
        return where
    fc = forecast(
        conn,
        lat=where[0],
        lon=where[1],
        when=_date(date),
        operator_group=operator_group,
    )
    return _compact_forecast(fc)


@_with_conn
def get_similar_incidents(
    conn,
    latitude=None,
    longitude=None,
    date=None,
    k=5,
    incident_id=None,
) -> dict[str, Any]:
    """Most similar past incidents (strictly before the reference date)."""
    k = max(1, min(int(k), 8))
    if incident_id:
        out = similar_to_incident(conn, incident_id, k)
    elif latitude is not None and longitude is not None:
        out = find_similar(
            conn, lat=float(latitude), lon=float(longitude), when=_date(date), k=k
        )
    else:
        return {"error": "Give latitude and longitude, or incident_id."}
    if "error" in out:
        return out
    keep = (
        "incident_number",
        "date",
        "place",
        "distance_km",
        "hazard_label",
        "similarity",
        "snippet",
    )
    return {
        "reference_date": out["reference_date"],
        "incidents": [{k_: r[k_] for k_ in keep} for r in out["incidents"]],
    }


@_with_conn
def get_crews_for_hazard(conn, hazard_group) -> dict[str, Any]:
    """Crews and equipment mapped to a hazard group, and which bases hold them."""
    if hazard_group not in MODEL_TARGETS:
        return {"error": f"Unknown hazard group {hazard_group!r}"}
    crews = get_crews(conn)
    entry = next(h for h in crews["hazard_map"] if h["hazard_group"] == hazard_group)
    out = []
    for c in entry["crews"]:
        bases = [
            b["name"] for b in crews["bases"] if c["crew_type_id"] in b["crew_types"]
        ]
        out.append(
            {
                "crew": c["crew_name"],
                "equipment": c["equipment"],
                "is_sample": c["is_sample"],
                "bases": bases,
            }
        )
    return {
        "hazard_group": hazard_group,
        "label": HAZARD_LABELS[hazard_group],
        "low_evidence": entry["low_evidence"],
        "crews": out,
        "sample_label": crews["sample_label"],
    }


@_with_conn
def get_readiness(
    conn,
    latitude=None,
    longitude=None,
    corridor=None,
    start=None,
    operator_group=None,
) -> dict[str, Any]:
    """7-day readiness: forecast mix, recommended crews, weather context, similar incidents."""
    where = _point(conn, latitude, longitude, corridor)
    if isinstance(where, dict):
        return where
    r = readiness(
        conn,
        lat=where[0],
        lon=where[1],
        start=_date(start),
        operator_group=operator_group,
    )
    weather = r["weather"]
    return {
        "week": r["week"],
        "place": corridor or None,
        "forecast": _compact_forecast(r["forecast"]),
        "recommended": [
            {
                "label": h["label"],
                "display": h["display"],
                "low_evidence_group": h["low_evidence_group"],
                "crews": [
                    {
                        "crew": c["crew_name"],
                        "equipment": c["equipment"],
                        "is_sample": c["is_sample"],
                        "nearest_base": None
                        if not c["nearest_base"]
                        else {
                            k: c["nearest_base"][k]
                            for k in (
                                "base_name",
                                "duration_min",
                                "distance_km",
                                "warning",
                            )
                        },
                    }
                    for c in h["crews"]
                ],
            }
            for h in r["recommended"]
        ],
        "sample_label": r["sample_label"],
        "weather": None
        if weather is None
        else {
            "source": weather["source"],
            "outlook_next_7_days": weather["outlook"],
            "prior_30_days": weather["prior_30_days"],
            "daily": weather["next_7_days"],
        },
        "weather_note": r["weather_note"],
        "weather_in_model": False,
        "similar": [
            {k: s[k] for k in ("date", "place", "hazard_label", "similarity")}
            for s in r["similar"]["incidents"][:3]
        ],
    }


@_with_conn
def get_dispatch_route(conn, latitude, longitude, hazard_group, k=3) -> dict[str, Any]:
    """Nearest crew bases with a matching crew, ranked by drive time (no geometry)."""
    out = dispatch(
        conn,
        lat=float(latitude),
        lon=float(longitude),
        hazard_group=hazard_group,
        k=max(1, min(int(k), 5)),
    )
    return {
        "hazard_label": out["hazard_label"],
        "sample_label": out["sample_label"],
        "message": out["message"],
        "bases": [
            {
                "base": b["base_name"],
                "is_sample": b["is_sample"],
                "crews": [c["crew_name"] for c in b["matching_crews"]],
                "duration_min": b["route"]["duration_min"],
                "distance_km": b["route"]["distance_km"],
                "provider": b["route"]["provider"],
                "warning": b["route"]["warning"],
                "last_mile_offroad_km": (b["route"]["last_mile"] or {}).get(
                    "distance_km"
                ),
            }
            for b in out["bases"]
        ],
    }


@_with_conn
def get_washout_insight(conn) -> dict[str, Any]:
    """Observed post-2022 Alberta washout pattern (not a model forecast)."""
    return washout_insight(conn)


def get_model_info() -> dict[str, Any]:
    """Held-out model performance in plain words (Canada and Alberta)."""
    info = model_info()
    if "error" in info:
        return info
    return {
        "plain_words": info["plain_words"],
        "canada_delta_log_loss_vs_best_baseline": info["canada"][
            "delta_log_loss_vs_best_baseline"
        ],
        "alberta_delta_log_loss_vs_best_baseline": info["alberta"][
            "delta_log_loss_vs_best_baseline"
        ],
        "test_period": info["split"]["test"],
    }


HAZARD_ENUM = {"type": "string", "enum": list(MODEL_TARGETS)}
_WHERE = {
    "latitude": {"type": "number"},
    "longitude": {"type": "number"},
    "corridor": {"type": "string", "description": "Ranking corridor name, e.g. Edson"},
}

FORECAST_TOOL_FUNCTIONS = {
    "get_forecast": get_forecast,
    "get_similar_incidents": get_similar_incidents,
    "get_crews_for_hazard": get_crews_for_hazard,
    "get_readiness": get_readiness,
    "get_dispatch_route": get_dispatch_route,
    "get_washout_insight": get_washout_insight,
    "get_model_info": get_model_info,
}

FORECAST_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_forecast",
        "description": "Hazard-type mix forecast for a point or corridor on a date (default "
        "today), with plain-word drivers, evidence counts and the low-evidence flag.",
        "input_schema": {
            "type": "object",
            "properties": {
                **_WHERE,
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "operator_group": {"type": "string"},
            },
        },
    },
    {
        "name": "get_similar_incidents",
        "description": "Most similar past incidents (only before the reference date) with "
        "date, place, hazard, similarity and a plain-English cause snippet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "date": {"type": "string"},
                "k": {"type": "integer", "default": 5},
                "incident_id": {"type": "string"},
            },
        },
    },
    {
        "name": "get_crews_for_hazard",
        "description": "Crews and equipment mapped to a hazard group (sample data until "
        "validated) and the crew bases that hold them.",
        "input_schema": {
            "type": "object",
            "properties": {"hazard_group": HAZARD_ENUM},
            "required": ["hazard_group"],
        },
    },
    {
        "name": "get_readiness",
        "description": "Readiness for the next 7 days at a point or corridor: forecast mix, "
        "recommended crews with nearest base and drive time, Open-Meteo weather context "
        "(not a model input), and similar past incidents.",
        "input_schema": {
            "type": "object",
            "properties": {
                **_WHERE,
                "start": {"type": "string", "description": "YYYY-MM-DD"},
                "operator_group": {"type": "string"},
            },
        },
    },
    {
        "name": "get_dispatch_route",
        "description": "Emergency dispatch: crew bases holding a crew for the hazard, ranked "
        "by drive time (OSRM / Mapbox / straight-line fallback).",
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "hazard_group": HAZARD_ENUM,
                "k": {"type": "integer", "default": 3},
            },
            "required": ["latitude", "longitude", "hazard_group"],
        },
    },
    {
        "name": "get_washout_insight",
        "description": "Observed post-2022 Alberta washout / ground-movement pattern with "
        "sample sizes. An observed pattern, not a forecast.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_model_info",
        "description": "How well the forecast model did on held-out 2022+ incidents, in "
        "plain words (Canada and Alberta).",
        "input_schema": {"type": "object", "properties": {}},
    },
]
