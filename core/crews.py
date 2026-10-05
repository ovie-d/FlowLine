"""Crew readiness: hazard -> crew -> equipment table, crew bases, dispatch ranking.

Seeded rows are SAMPLE data (is_sample = true, "Sample — to be validated").
Rows a planner saves through PUT /crews/map are stored with is_sample = false.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import psycopg

from core.routing import Point, rank_by_drive_time, route
from core.taxonomy import HAZARD_LABELS, LOW_EVIDENCE_GROUPS, MODEL_TARGETS

MAX_EQUIPMENT_ITEMS = 20
MAX_TEXT = 120
SAMPLE_LABEL = "Sample — to be validated"

RouteFn = Callable[[Point, Point], dict[str, Any]]


class CrewMapError(ValueError):
    """Invalid crew-map edit (bad hazard group, crew type or equipment)."""


def get_crews(conn: psycopg.Connection) -> dict[str, Any]:
    types = conn.execute(
        "SELECT id, name, description, is_sample FROM crew_types ORDER BY name"
    ).fetchall()
    mapping = conn.execute(
        "SELECT m.hazard_group, m.crew_type_id, t.name, m.equipment, m.priority, "
        "m.is_sample, m.updated_at FROM hazard_crew_map m JOIN crew_types t "
        "ON t.id = m.crew_type_id ORDER BY m.hazard_group, m.priority, t.name"
    ).fetchall()
    bases = conn.execute(
        "SELECT id, name, province, latitude, longitude, crew_types, is_sample "
        "FROM crew_bases ORDER BY name"
    ).fetchall()
    by_hazard: dict[str, list[dict[str, Any]]] = {h: [] for h in MODEL_TARGETS}
    for m in mapping:
        by_hazard.setdefault(m["hazard_group"], []).append(
            {
                "crew_type_id": m["crew_type_id"],
                "crew_name": m["name"],
                "equipment": list(m["equipment"]),
                "priority": m["priority"],
                "is_sample": m["is_sample"],
                "updated_at": m["updated_at"].isoformat(),
            }
        )
    rows = [*types, *mapping, *bases]
    return {
        "sample_label": SAMPLE_LABEL,
        "has_sample_data": any(r["is_sample"] for r in rows),
        "crew_types": [dict(t) for t in types],
        "hazard_map": [
            {
                "hazard_group": h,
                "hazard_label": HAZARD_LABELS[h],
                "low_evidence": h in LOW_EVIDENCE_GROUPS,
                "crews": crews,
            }
            for h, crews in by_hazard.items()
        ],
        "bases": [dict(b) | {"crew_types": list(b["crew_types"])} for b in bases],
    }


def _clean_equipment(items: list[str]) -> list[str]:
    cleaned = [str(i).strip()[:MAX_TEXT] for i in items if str(i).strip()]
    if len(cleaned) > MAX_EQUIPMENT_ITEMS:
        raise CrewMapError(f"at most {MAX_EQUIPMENT_ITEMS} equipment items per crew")
    return list(dict.fromkeys(cleaned))


def update_crew_map(
    conn: psycopg.Connection, hazard_group: str, crews: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace the crews (and equipment) recommended for one hazard group."""
    if hazard_group not in MODEL_TARGETS:
        raise CrewMapError(f"unknown hazard group {hazard_group!r}")
    known = {r["id"] for r in conn.execute("SELECT id FROM crew_types")}
    ids = [c["crew_type_id"] for c in crews]
    unknown = sorted(set(ids) - known)
    if unknown:
        raise CrewMapError(f"unknown crew type(s): {', '.join(unknown)}")
    if len(set(ids)) != len(ids):
        raise CrewMapError("each crew type may appear once per hazard group")
    rows = [
        (
            hazard_group,
            c["crew_type_id"],
            _clean_equipment(c.get("equipment", [])),
            int(c.get("priority", i + 1)),
        )
        for i, c in enumerate(crews)
    ]
    with conn.transaction():
        conn.execute(
            "DELETE FROM hazard_crew_map WHERE hazard_group = %s", (hazard_group,)
        )
        conn.cursor().executemany(
            "INSERT INTO hazard_crew_map (hazard_group, crew_type_id, equipment, priority, "
            "is_sample, updated_at) VALUES (%s, %s, %s, %s, false, now())",
            rows,
        )
    return next(
        h["crews"]
        for h in get_crews(conn)["hazard_map"]
        if h["hazard_group"] == hazard_group
    )


def dispatch(
    conn: psycopg.Connection,
    *,
    lat: float,
    lon: float,
    hazard_group: str,
    k: int = 3,
    route_fn: RouteFn | None = None,
) -> dict[str, Any]:
    """Crew bases holding a crew mapped to `hazard_group`, ranked by drive time."""
    if hazard_group not in MODEL_TARGETS:
        raise CrewMapError(f"unknown hazard group {hazard_group!r}")
    needed = {
        r["crew_type_id"]: r["name"]
        for r in conn.execute(
            "SELECT m.crew_type_id, t.name FROM hazard_crew_map m "
            "JOIN crew_types t ON t.id = m.crew_type_id WHERE m.hazard_group = %s",
            (hazard_group,),
        )
    }
    bases = conn.execute(
        "SELECT id, name, latitude, longitude, crew_types, is_sample FROM crew_bases "
        "WHERE crew_types && %s::text[]",
        (list(needed),),
    ).fetchall()
    route_fn = route_fn or (lambda a, b: route(a, b))
    incident = Point(lat, lon)
    results = [
        {
            "base_id": b["id"],
            "base_name": b["name"],
            "is_sample": b["is_sample"],
            "latitude": b["latitude"],
            "longitude": b["longitude"],
            "matching_crews": [
                {"crew_type_id": c, "crew_name": needed[c]}
                for c in b["crew_types"]
                if c in needed
            ],
            "route": route_fn(Point(b["latitude"], b["longitude"]), incident),
        }
        for b in bases
    ]
    ranked = rank_by_drive_time(results)[:k]
    return {
        "incident": {"latitude": lat, "longitude": lon},
        "hazard_group": hazard_group,
        "hazard_label": HAZARD_LABELS[hazard_group],
        "sample_label": SAMPLE_LABEL,
        "bases": ranked,
        "message": None
        if ranked
        else "No crew base holds a crew mapped to this hazard.",
    }
