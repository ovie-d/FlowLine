"""Similar past incidents by structured context (pgvector), as forecast evidence.

Public CER data has cause codes, not narratives, so similarity is computed on a
context vector — where, when in the year, under what weather, carrying what —
never on the incident's cause or outcome. The narrative path (core/narratives.py)
is ready for operator incident narratives in a pilot.

Rule: a search for a forecast returns only incidents strictly *before* its
reference date; a search seeded by an incident excludes that incident and
anything on or after its date.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import psycopg

from core.taxonomy import HAZARD_LABELS

# Design scales (documented choices, not fitted): one vector unit equals …
GEO_SCALE_KM = 100.0  # … 100 km apart
SEASON_SCALE_DAYS = 30.0  # … 30 days apart in the calendar year
WEATHER_SCALES: dict[str, float] = {  # … this much difference in the variable
    "temp_mean_7d": 10.0,  # °C
    "precip_30d": 50.0,  # mm
    "freeze_thaw_30d": 10.0,  # days
    "snow_on_ground_d0": 20.0,  # cm
}
WEATHER_WEIGHT = 0.5
COMMODITIES: tuple[str, ...] = ("gas", "liquid")
EARTH_RADIUS_KM = 6371.0088
VECTOR_DIM = 3 + 2 + len(WEATHER_SCALES) + len(COMMODITIES)
SNIPPET_MAX_CHARS = 220


def _season_scale() -> float:
    chord = 2 * math.sin(math.pi * SEASON_SCALE_DAYS / 365.25)
    return 1.0 / chord


def context_vector(
    lat: float,
    lon: float,
    when: date,
    weather: dict[str, float | None] | None,
    commodity: str | None,
    fallback: dict[str, float],
) -> tuple[list[float], bool]:
    """Vector for a context, plus whether every weather value was known.

    Unknown weather values use `fallback` (national medians) so they neither
    attract nor repel matches; callers surface the returned flag.
    """
    phi, lam = math.radians(lat), math.radians(lon)
    geo = EARTH_RADIUS_KM / GEO_SCALE_KM
    xyz = [
        geo * math.cos(phi) * math.cos(lam),
        geo * math.cos(phi) * math.sin(lam),
        geo * math.sin(phi),
    ]
    angle = 2 * math.pi * (when.timetuple().tm_yday - 1) / 365.25
    season = [_season_scale() * math.sin(angle), _season_scale() * math.cos(angle)]
    known = True
    wx: list[float] = []
    for name, scale in WEATHER_SCALES.items():
        value = (weather or {}).get(name)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            value, known = fallback[name], False
        wx.append(WEATHER_WEIGHT * float(value) / scale)
    onehot = [1.0 if commodity == c else 0.0 for c in COMMODITIES]
    return xyz + season + wx + onehot, known


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


def similarity_from_distance(dist: float) -> float:
    """Map vector distance to 0–1 (1 = identical context)."""
    return round(1.0 / (1.0 + dist), 3)


def _plain(code: str) -> str:
    """'Damage or deterioration mechanism, Equipment, Valve Seals' -> 'Equipment — valve seals'."""
    parts = [p.strip() for p in code.split(",") if p.strip()]
    if parts and parts[0] in {
        "Damage or deterioration mechanism",
        "Substandard Acts",
        "Substandard Conditions",
        "Job or system factors",
        "Personal factors",
    }:
        parts = parts[1:]
    if not parts:
        return ""
    head = parts[0]
    rest = [
        " ".join(w if w.isupper() else w.lower() for w in p.split()) for p in parts[1:]
    ]
    return head + (" — " + ", ".join(rest) if rest else "")


def cause_summary(detailed_what: str | None, detailed_why: str | None) -> str:
    """Plain-English rendering of the CER cause codes (display only)."""
    what = [_plain(c) for c in str(detailed_what or "").split(";") if _plain(c)]
    why = [_plain(c) for c in str(detailed_why or "").split(";") if _plain(c)]
    text = ""
    if what:
        text += "What happened: " + "; ".join(dict.fromkeys(what)) + "."
    if why:
        text += (" " if text else "") + "Why: " + "; ".join(dict.fromkeys(why)) + "."
    if len(text) > SNIPPET_MAX_CHARS:
        text = text[: SNIPPET_MAX_CHARS - 1].rstrip() + "…"
    return text or "Cause codes not recorded."


SIMILAR_SQL = """
SELECT i.incident_number, i.event_date, i.nearest_centre, i.province,
       i.latitude, i.longitude, i.hazard_group, i.is_model_target,
       i.detailed_what, i.detailed_why, c.weather_known,
       ST_Distance(i.geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography)
         / 1000.0 AS distance_km,
       c.vec <-> %(vec)s::vector AS dist
FROM incident_context c
JOIN incidents i USING (incident_number)
WHERE i.event_date < %(before)s
  AND (%(exclude)s::text IS NULL OR i.incident_number <> %(exclude)s::text)
ORDER BY c.vec <-> %(vec)s::vector
LIMIT %(k)s
"""


def _row_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "incident_number": row["incident_number"],
        "date": row["event_date"].isoformat(),
        "place": (row["nearest_centre"] or "").strip() or row["province"],
        "province": row["province"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "distance_km": round(float(row["distance_km"]), 1),
        "hazard_group": row["hazard_group"],
        "hazard_label": HAZARD_LABELS[row["hazard_group"]],
        "is_model_target": bool(row["is_model_target"]),
        "similarity": similarity_from_distance(float(row["dist"])),
        "weather_known": bool(row["weather_known"]),
        "snippet": cause_summary(row["detailed_what"], row["detailed_why"]),
    }


def weather_fallback(conn: psycopg.Connection) -> dict[str, float]:
    row = conn.execute("SELECT medians FROM similarity_meta WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("similarity_meta missing — run scripts.load_postgres")
    return {k: float(v) for k, v in row["medians"].items()}


def find_similar(
    conn: psycopg.Connection,
    *,
    lat: float,
    lon: float,
    when: date,
    weather: dict[str, float | None] | None = None,
    commodity: str | None = None,
    k: int = 5,
) -> dict[str, Any]:
    """Top-k past incidents (strictly before `when`) most similar to a context."""
    vec, known = context_vector(
        lat, lon, when, weather, commodity, weather_fallback(conn)
    )
    rows = conn.execute(
        SIMILAR_SQL,
        {
            "lat": lat,
            "lon": lon,
            "vec": vector_literal(vec),
            "before": when,
            "exclude": None,
            "k": k,
        },
    ).fetchall()
    return {
        "reference_date": when.isoformat(),
        "query_weather_known": known,
        "incidents": [_row_out(r) for r in rows],
    }


def similar_to_incident(
    conn: psycopg.Connection, incident_number: str, k: int = 5
) -> dict[str, Any]:
    """Top-k incidents before the given incident's date, most similar to its context."""
    seed = conn.execute(
        "SELECT i.latitude, i.longitude, i.event_date, c.vec::text AS vec "
        "FROM incidents i JOIN incident_context c USING (incident_number) "
        "WHERE i.incident_number = %s",
        (incident_number,),
    ).fetchone()
    if seed is None:
        return {"error": f"unknown incident {incident_number!r}"}
    rows = conn.execute(
        SIMILAR_SQL,
        {
            "lat": seed["latitude"],
            "lon": seed["longitude"],
            "vec": seed["vec"],
            "before": seed["event_date"],
            "exclude": incident_number,
            "k": k,
        },
    ).fetchall()
    return {
        "reference_date": seed["event_date"].isoformat(),
        "seed_incident": incident_number,
        "incidents": [_row_out(r) for r in rows],
    }
