"""GET /crews, PUT /crews/map, POST /dispatch/route (throwaway Postgres DB)."""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.main import app
from core import crews
from core.taxonomy import GEOTECHNICAL, MODEL_TARGETS, THIRD_PARTY
from scripts import load_postgres


def fake_route(origin, incident) -> dict:
    # Drive time proportional to straight-line distance, so ranking is predictable.
    from core.geo import haversine_km

    km = float(haversine_km(origin.lat, origin.lon, incident.lat, incident.lon))
    return {
        "provider": "fake",
        "duration_min": round(km, 1),
        "distance_km": round(km, 1),
        "geometry": None,
        "last_mile": None,
        "warning": None,
        "fallbacks": [],
    }


@pytest.fixture
def api(pg_env: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    with psycopg.connect(pg_env, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("TRUNCATE crew_types, hazard_crew_map, crew_bases CASCADE")
        load_postgres.seed_crews(conn)
        conn.commit()
    monkeypatch.setattr(crews, "route", fake_route)
    with TestClient(app) as client:
        yield client


def test_get_crews_flags_sample_data(api: TestClient) -> None:
    body = api.get("/crews").json()
    assert body["has_sample_data"] is True
    assert body["sample_label"] == "Sample — to be validated"
    assert [h["hazard_group"] for h in body["hazard_map"]] == list(MODEL_TARGETS)
    third = next(h for h in body["hazard_map"] if h["hazard_group"] == THIRD_PARTY)
    assert third["low_evidence"] is True and third["crews"]
    assert len(body["bases"]) == 8


def test_put_crews_map_replaces_and_marks_planner_rows(api: TestClient) -> None:
    payload = {
        "hazard_group": GEOTECHNICAL,
        "crews": [
            {
                "crew_type_id": "geotechnical",
                "equipment": ["GNSS", " GNSS ", "Drone", ""],
            },
        ],
    }
    r = api.put("/crews/map", json=payload)
    assert r.status_code == 200
    saved = r.json()["crews"]
    assert len(saved) == 1 and saved[0]["equipment"] == ["GNSS", "Drone"]
    assert saved[0]["is_sample"] is False
    geo = next(
        h
        for h in api.get("/crews").json()["hazard_map"]
        if h["hazard_group"] == GEOTECHNICAL
    )
    assert [c["crew_type_id"] for c in geo["crews"]] == ["geotechnical"]


@pytest.mark.parametrize(
    "payload",
    [
        {"hazard_group": "not_a_group", "crews": []},
        {"hazard_group": GEOTECHNICAL, "crews": [{"crew_type_id": "astronauts"}]},
        {"hazard_group": GEOTECHNICAL, "crews": [{"crew_type_id": "geotechnical"}] * 2},
        {
            "hazard_group": GEOTECHNICAL,
            "crews": [{"crew_type_id": "geotechnical", "equipment": ["x"] * 21}],
        },
    ],
)
def test_put_crews_map_rejects_bad_edits(api: TestClient, payload: dict) -> None:
    assert api.put("/crews/map", json=payload).status_code == 422


def test_dispatch_ranks_matching_bases_by_drive_time(api: TestClient) -> None:
    near_edson = {
        "latitude": 53.62,
        "longitude": -116.6,
        "hazard_group": GEOTECHNICAL,
        "k": 3,
    }
    body = api.post("/dispatch/route", json=near_edson).json()
    names = [b["base_name"] for b in body["bases"]]
    assert names[0] == "Edson"
    times = [b["route"]["duration_min"] for b in body["bases"]]
    assert times == sorted(times)
    for base in body["bases"]:
        assert {c["crew_type_id"] for c in base["matching_crews"]} & {
            "geotechnical",
            "civil_erosion",
        }
        assert base["is_sample"] is True


def test_dispatch_validation(api: TestClient) -> None:
    assert (
        api.post(
            "/dispatch/route",
            json={"latitude": 53, "longitude": -116, "hazard_group": "nope"},
        ).status_code
        == 422
    )
    assert (
        api.post(
            "/dispatch/route",
            json={"latitude": 95, "longitude": -116, "hazard_group": GEOTECHNICAL},
        ).status_code
        == 422
    )


def test_endpoints_503_without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    with TestClient(app) as client:
        r = client.get("/crews")
    assert r.status_code == 503 and "docker compose up -d db" in r.json()["detail"]
