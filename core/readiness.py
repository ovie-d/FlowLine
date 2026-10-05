"""Readiness for an area and the next 7 days: forecast mix + crews + evidence + weather.

Every number comes from the database, the model, the crew table, the router or
Open-Meteo. Weather is context only (not a model input).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import psycopg

from core import openmeteo
from core.crews import SAMPLE_LABEL, get_crews
from core.forecast import forecast
from core.routing import Point, route
from core.similar import find_similar

RECOMMEND_MIN_PROBABILITY = 0.10
MAX_RECOMMENDED_HAZARDS = 3
WEEK_DAYS = 7
SIMILAR_K = 5

RouteFn = Callable[[Point, Point], dict[str, Any]]
WeatherFn = Callable[[float, float, date], list[dict[str, Any]]]


def _recommended_hazards(hazards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    picked = [h for h in hazards if h["probability"] >= RECOMMEND_MIN_PROBABILITY]
    return (picked or hazards[:1])[:MAX_RECOMMENDED_HAZARDS]


def _fastest_base_per_crew(
    bases: list[dict[str, Any]],
    lat: float,
    lon: float,
    route_fn: RouteFn,
    crew_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """For each crew type, the base holding it with the shortest drive (one route per base)."""
    incident = Point(lat, lon)
    routed = [
        (b, route_fn(Point(b["latitude"], b["longitude"]), incident))
        for b in bases
        if set(b["crew_types"]) & crew_ids
    ]

    def sort_key(item: tuple[dict[str, Any], dict[str, Any]]) -> tuple[bool, float]:
        r = item[1]
        return (r["duration_min"] is None, r["duration_min"] or r["distance_km"])

    best: dict[str, dict[str, Any]] = {}
    for base, r in sorted(routed, key=sort_key):
        for crew in base["crew_types"]:
            if crew in crew_ids and crew not in best:
                best[crew] = {
                    "base_id": base["id"],
                    "base_name": base["name"],
                    "is_sample": base["is_sample"],
                    "duration_min": r["duration_min"],
                    "distance_km": r["distance_km"],
                    "provider": r["provider"],
                    "warning": r["warning"],
                }
    return best


def readiness(
    conn: psycopg.Connection,
    *,
    lat: float,
    lon: float,
    start: date,
    operator_group: str | None = None,
    weather_fn: WeatherFn | None = None,
    route_fn: RouteFn | None = None,
) -> dict[str, Any]:
    weather_fn = weather_fn or (lambda la, lo, d: openmeteo.fetch_daily(la, lo, d))
    route_fn = route_fn or (lambda a, b: route(a, b))
    mid = start + timedelta(days=WEEK_DAYS // 2)
    fc = forecast(conn, lat=lat, lon=lon, when=mid, operator_group=operator_group)
    try:
        weather = openmeteo.summarize(weather_fn(lat, lon, start), start)
        weather_note = None
    except openmeteo.WeatherUnavailable as exc:
        weather, weather_note = None, f"Weather unavailable (offline?): {exc}"
    top = _recommended_hazards(fc["hazards"])
    crews = get_crews(conn)
    by_hazard = {h["hazard_group"]: h["crews"] for h in crews["hazard_map"]}
    crew_ids = {
        c["crew_type_id"] for h in top for c in by_hazard.get(h["hazard_group"], [])
    }
    nearest = _fastest_base_per_crew(crews["bases"], lat, lon, route_fn, crew_ids)
    recommended = [
        {
            "hazard_group": h["hazard_group"],
            "label": h["label"],
            "probability": h["probability"],
            "display": h["display"],
            "low_evidence_group": h["low_evidence_group"],
            "crews": [
                {**c, "nearest_base": nearest.get(c["crew_type_id"])}
                for c in by_hazard.get(h["hazard_group"], [])
            ],
        }
        for h in top
    ]
    similar = find_similar(
        conn,
        lat=lat,
        lon=lon,
        when=start,
        weather=weather["similarity_weather"] if weather else None,
        commodity=fc["context"]["commodity"],
        k=SIMILAR_K,
    )
    return {
        "location": fc["location"],
        "week": {
            "start": start.isoformat(),
            "end": (start + timedelta(days=WEEK_DAYS - 1)).isoformat(),
            "forecast_date": mid.isoformat(),
        },
        "forecast": fc,
        "recommended": recommended,
        "recommend_rule": f"hazards with probability >= {RECOMMEND_MIN_PROBABILITY:.0%} "
        f"(max {MAX_RECOMMENDED_HAZARDS})",
        "sample_label": SAMPLE_LABEL,
        "weather": weather,
        "weather_note": weather_note,
        "weather_in_model": False,
        "similar": similar,
    }
