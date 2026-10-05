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
                    "hazard_group": r["hazard_group"],
                    "hazard_label": HAZARD_LABELS[r["hazard_group"]],
                    "place": place_name(r["nearest_centre"], r["province"]),
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
