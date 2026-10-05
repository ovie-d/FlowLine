"""Read-only map layers: corridors, incident points, national pipeline systems."""

from __future__ import annotations

import json
from typing import Any

import psycopg

from core.similar import place_name
from core.taxonomy import HAZARD_LABELS


def corridors(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Ranking corridors (cleaned names) with centroids — for area search."""
    rows = conn.execute(
        "SELECT name, n_incidents, latitude, longitude FROM corridors ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def incident_points(conn: psycopg.Connection) -> dict[str, Any]:
    """All incidents as GeoJSON points coloured by hazard group (no cause text)."""
    rows = conn.execute(
        "SELECT incident_number, event_date, latitude, longitude, hazard_group, province, "
        "nearest_centre FROM incidents ORDER BY event_date"
    ).fetchall()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [r["longitude"], r["latitude"]],
                },
                "properties": {
                    "id": r["incident_number"],
                    "date": r["event_date"].isoformat(),
                    "year": r["event_date"].year,
                    "hazard_group": r["hazard_group"],
                    "hazard_label": HAZARD_LABELS[r["hazard_group"]],
                    "place": place_name(r["nearest_centre"], r["province"]),
                },
            }
            for r in rows
        ],
    }


UNDETERMINED = {"", "to be determined", "unknown"}


def plain_codes(text: str | None) -> list[str]:
    """CER cause codes in plain English: the most specific part of each code, deduplicated.

    "Damage or deterioration mechanism, External Interference, Third Party;
    Substandard Conditions, Weather Related, Adverse weather" -> ["Third Party", "Adverse weather"]
    """
    out: list[str] = []
    for code in (text or "").split(";"):
        leaf = code.split(",")[-1].strip()
        if leaf.lower() in UNDETERMINED:
            continue
        leaf = leaf[0].upper() + leaf[1:]
        if leaf not in out:
            out.append(leaf)
    return out


def _categories(text: str | None) -> list[str]:
    return [
        c.strip()
        for c in (text or "").split(",")
        if c.strip().lower() not in UNDETERMINED
    ]


def incident_detail(
    conn: psycopg.Connection, incident_number: str
) -> dict[str, Any] | None:
    """One incident for the map popup: date, place, hazard, operator, CER cause codes."""
    r = conn.execute(
        "SELECT incident_number, event_date, event_date_source, province, nearest_centre, "
        "company, operator_group, commodity, status, latitude, longitude, hazard_group, "
        "incident_types, what_category, detailed_what, why_category, detailed_why "
        "FROM incidents WHERE incident_number = %s",
        (incident_number,),
    ).fetchone()
    if r is None:
        return None
    what = _categories(r["what_category"])
    why = _categories(r["why_category"])
    return {
        "incident_number": r["incident_number"],
        "date": r["event_date"].isoformat(),
        "date_source": r["event_date_source"],
        "place": place_name(r["nearest_centre"], r["province"]),
        "province": r["province"],
        "latitude": float(r["latitude"]),
        "longitude": float(r["longitude"]),
        "hazard_group": r["hazard_group"],
        "hazard_label": HAZARD_LABELS[r["hazard_group"]],
        "operator": r["company"],
        "operator_group": r["operator_group"],
        "commodity": r["commodity"],
        "status": r["status"],
        "incident_types": [
            t.strip() for t in (r["incident_types"] or "").split(",") if t.strip()
        ],
        "what_happened": what,
        "what_detail": plain_codes(r["detailed_what"]),
        "why": why,
        "why_detail": plain_codes(r["detailed_why"]),
        "cause_determined": bool(what or why),
        "source": "CER pipeline incident data (cause codes as reported)",
    }


def waterway_crossings(conn: psycopg.Connection) -> dict[str, Any]:
    """Pipeline–waterway crossings (OSM, Alberta) if scripts.washout_crossings has run."""
    exists = conn.execute(
        "SELECT to_regclass('public.waterway_crossings') IS NOT NULL AS ok"
    ).fetchone()["ok"]
    if not exists:
        return {
            "type": "FeatureCollection",
            "features": [],
            "available": False,
            "note": "Run python -m scripts.washout_crossings to build the crossings layer.",
        }
    rows = conn.execute(
        "SELECT id, kind, pipeline_name, ST_X(geom) AS lon, ST_Y(geom) AS lat "
        "FROM waterway_crossings ORDER BY id"
    ).fetchall()
    return {
        "type": "FeatureCollection",
        "available": True,
        "note": "Pipeline–waterway crossings from OpenStreetMap and CER pipeline systems.",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(r["lon"], 5), round(r["lat"], 5)],
                },
                "properties": {
                    "id": r["id"],
                    "kind": r["kind"],
                    "pipeline": r["pipeline_name"],
                },
            }
            for r in rows
        ],
    }


def pipelines(conn: psycopg.Connection, simplify_deg: float = 0.01) -> dict[str, Any]:
    """CER pipeline systems as GeoJSON (display only)."""
    rows = conn.execute(
        "SELECT pipeline_name, company, commodity, "
        "ST_AsGeoJSON(ST_Simplify(geom::geometry, %s), 4) AS g FROM pipelines",
        (simplify_deg,),
    ).fetchall()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(r["g"]),
                "properties": {
                    "name": r["pipeline_name"],
                    "company": r["company"],
                    "commodity": r["commodity"],
                },
            }
            for r in rows
        ],
    }
