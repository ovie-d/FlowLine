"""Routing provider chain and fallbacks (no network: httpx.MockTransport)."""

from __future__ import annotations

import httpx
import pytest

from core import routing
from core.routing import Point, rank_by_drive_time, route

EDSON = Point(53.5817, -116.4396)
SITE = Point(53.70, -116.90)


def osrm_payload(
    duration_s: float = 3600,
    distance_m: float = 60000,
    snap_m: float = 50,
    code: str = "Ok",
) -> dict:
    return {
        "code": code,
        "routes": []
        if code != "Ok"
        else [
            {
                "duration": duration_s,
                "distance": distance_m,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-116.44, 53.58], [-116.88, 53.69]],
                },
            }
        ],
        "waypoints": [
            {"location": [-116.44, 53.58], "distance": 10.0},
            {"location": [-116.88, 53.69], "distance": snap_m},
        ],
    }


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_MAPBOX_TOKEN", raising=False)
    monkeypatch.setenv("OSRM_URL", "http://osrm.test")


def test_osrm_route_shape_and_units() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return httpx.Response(200, json=osrm_payload(duration_s=5400, distance_m=98765))

    out = route(EDSON, SITE, client_for(handler))
    assert out["provider"] == "osrm"
    assert out["duration_min"] == 90.0 and out["distance_km"] == 98.8
    assert out["last_mile"] is None and out["warning"] is None
    assert (
        "/route/v1/driving/-116.439600,53.581700;-116.900000,53.700000" in seen["url"]
    )


def test_offroad_last_mile_is_reported() -> None:
    out = route(
        EDSON,
        SITE,
        client_for(lambda r: httpx.Response(200, json=osrm_payload(snap_m=3400))),
    )
    assert out["last_mile"]["label"] == "last-mile, off-road"
    assert out["last_mile"]["distance_km"] == 3.4
    assert out["last_mile"]["geometry"]["coordinates"][-1] == [SITE.lon, SITE.lat]


def test_osrm_down_falls_back_to_mapbox_when_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAPBOX_TOKEN", "pk.test")

    def osrm(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    def mapbox(req: httpx.Request) -> httpx.Response:
        assert req.url.host == "api.mapbox.com"
        assert req.url.params["access_token"] == "pk.test"
        return httpx.Response(200, json=osrm_payload(duration_s=600))

    out = route(EDSON, SITE, client_for(osrm), client_for(mapbox))
    assert out["provider"] == "mapbox" and out["duration_min"] == 10.0
    assert out["fallbacks"] and out["fallbacks"][0].startswith("osrm")


def test_nothing_available_gives_straight_line_with_warning() -> None:
    def down(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    out = route(EDSON, SITE, client_for(down))
    assert out["provider"] == "straight_line"
    assert out["duration_min"] is None  # never invent a drive time
    assert out["distance_km"] == pytest.approx(33.6, abs=0.5)
    assert "straight-line" in out["warning"]
    assert out["fallbacks"] == ["osrm: ConnectError", "mapbox: no token"]


def test_no_road_nearby_is_not_a_route() -> None:
    far_snap = osrm_payload(snap_m=routing.MAX_SNAP_KM * 1000 + 1)
    out = route(EDSON, SITE, client_for(lambda r: httpx.Response(200, json=far_snap)))
    assert out["provider"] == "straight_line"


def test_osrm_no_route_code_falls_back() -> None:
    out = route(
        EDSON,
        SITE,
        client_for(lambda r: httpx.Response(400, json=osrm_payload(code="NoRoute"))),
    )
    assert out["provider"] == "straight_line"
    assert out["fallbacks"][0] == "osrm: NoRoute"


def test_ranking_puts_timed_routes_before_straight_line() -> None:
    rows = [
        {"name": "a", "route": {"duration_min": None, "distance_km": 5.0}},
        {"name": "b", "route": {"duration_min": 80.0, "distance_km": 90.0}},
        {"name": "c", "route": {"duration_min": 30.0, "distance_km": 40.0}},
    ]
    assert [r["name"] for r in rank_by_drive_time(rows)] == ["c", "b", "a"]
