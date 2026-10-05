"""Drive time and route geometry from crew bases to an incident.

Provider chain:
1. OSRM (local, Alberta car profile; OSRM_URL, default http://localhost:5000)
2. Mapbox Directions (only if MAPBOX_TOKEN / NEXT_PUBLIC_MAPBOX_TOKEN is set)
3. Straight-line distance with a clear warning — no drive time is invented.

Remote incidents may be off-road: the router snaps the incident to the nearest
routable road; the remaining straight-line gap is reported as "last-mile, off-road".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from core.geo import haversine_km

DEFAULT_OSRM_URL = "http://localhost:5000"
MAPBOX_URL = "https://api.mapbox.com/directions/v5/mapbox/driving"
TIMEOUT_S = 5.0
OFFROAD_MIN_KM = 0.2  # gaps shorter than this are normal snapping noise
MAX_SNAP_KM = 50.0  # beyond this the router has no roads here (e.g. outside Alberta)
STRAIGHT_LINE_WARNING = (
    "No road router available — straight-line distance only, no drive time. "
    "Start OSRM (docker compose up -d osrm) or set a Mapbox token."
)
PREPARING_WARNING = (
    "Road routing is still being prepared in the background (first run, several "
    "minutes) — straight-line distance only, no drive time, until it is ready."
)
# Written by scripts/background_setup.sh (.ps1) while the OSRM data is downloaded and built.
ROUTING_BUILDING_MARKER = (
    Path(__file__).resolve().parent.parent / ".run" / "routing-building"
)


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float

    def coord(self) -> str:
        return f"{self.lon:.6f},{self.lat:.6f}"


class RoutingUnavailable(Exception):
    """A provider could not produce a usable route."""


def osrm_url() -> str:
    return os.environ.get("OSRM_URL", "").strip() or DEFAULT_OSRM_URL


def mapbox_token() -> str | None:
    for name in ("MAPBOX_TOKEN", "NEXT_PUBLIC_MAPBOX_TOKEN"):
        token = os.environ.get(name, "").strip()
        if token:
            return token
    return None


def _last_mile(
    incident: Point, snapped: list[float], snap_m: float
) -> dict[str, Any] | None:
    km = snap_m / 1000.0
    if km < OFFROAD_MIN_KM:
        return None
    return {
        "label": "last-mile, off-road",
        "distance_km": round(km, 2),
        "geometry": {
            "type": "LineString",
            "coordinates": [snapped, [incident.lon, incident.lat]],
        },
    }


def _from_payload(
    payload: dict[str, Any], provider: str, incident: Point
) -> dict[str, Any]:
    """Shared OSRM / Mapbox response shape -> our route dict."""
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingUnavailable(f"{provider}: {payload.get('code', 'no route')}")
    route = payload["routes"][0]
    origin_wp, incident_wp = payload["waypoints"][0], payload["waypoints"][-1]
    snap_m = float(incident_wp.get("distance") or 0.0)
    if (
        snap_m / 1000.0 > MAX_SNAP_KM
        or float(origin_wp.get("distance") or 0) / 1000 > MAX_SNAP_KM
    ):
        raise RoutingUnavailable(f"{provider}: no road within {MAX_SNAP_KM:.0f} km")
    return {
        "provider": provider,
        "duration_min": round(float(route["duration"]) / 60.0, 1),
        "distance_km": round(float(route["distance"]) / 1000.0, 1),
        "geometry": route["geometry"],
        "last_mile": _last_mile(incident, incident_wp["location"], snap_m),
        "warning": None,
    }


def route_osrm(origin: Point, incident: Point, client: httpx.Client) -> dict[str, Any]:
    url = f"{osrm_url()}/route/v1/driving/{origin.coord()};{incident.coord()}"
    try:
        resp = client.get(url, params={"overview": "full", "geometries": "geojson"})
    except httpx.HTTPError as exc:
        raise RoutingUnavailable(f"osrm: {exc.__class__.__name__}") from exc
    if resp.status_code >= 500:
        raise RoutingUnavailable(f"osrm: HTTP {resp.status_code}")
    return _from_payload(resp.json(), "osrm", incident)


def route_mapbox(
    origin: Point, incident: Point, client: httpx.Client
) -> dict[str, Any]:
    token = mapbox_token()
    if not token:
        raise RoutingUnavailable("mapbox: no token")
    url = f"{MAPBOX_URL}/{origin.coord()};{incident.coord()}"
    params = {"overview": "full", "geometries": "geojson", "access_token": token}
    try:
        resp = client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise RoutingUnavailable(f"mapbox: {exc.__class__.__name__}") from exc
    if resp.status_code != 200:
        raise RoutingUnavailable(f"mapbox: HTTP {resp.status_code}")
    return _from_payload(resp.json(), "mapbox", incident)


def route_straight(origin: Point, incident: Point) -> dict[str, Any]:
    km = float(haversine_km(origin.lat, origin.lon, incident.lat, incident.lon))
    return {
        "provider": "straight_line",
        "duration_min": None,
        "distance_km": round(km, 1),
        "geometry": {
            "type": "LineString",
            "coordinates": [[origin.lon, origin.lat], [incident.lon, incident.lat]],
        },
        "last_mile": None,
        "warning": PREPARING_WARNING
        if ROUTING_BUILDING_MARKER.exists()
        else STRAIGHT_LINE_WARNING,
    }


def route(
    origin: Point,
    incident: Point,
    client: httpx.Client | None = None,
    mapbox_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Best available route; records which providers failed and why."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S)
    failures: list[str] = []
    try:
        for provider, http in (
            (route_osrm, client),
            (route_mapbox, mapbox_client or client),
        ):
            try:
                out = provider(origin, incident, http)
                out["fallbacks"] = failures
                return out
            except RoutingUnavailable as exc:
                failures.append(str(exc))
    finally:
        if own:
            client.close()
    out = route_straight(origin, incident)
    out["fallbacks"] = failures
    return out


def rank_by_drive_time(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order base routes by drive time; straight-line results sort by distance, last."""
    return sorted(
        routes,
        key=lambda r: (
            r["route"]["duration_min"] is None,
            r["route"]["duration_min"]
            if r["route"]["duration_min"] is not None
            else r["route"]["distance_km"],
        ),
    )
