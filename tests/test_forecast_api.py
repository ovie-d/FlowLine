"""POST /forecast, GET /similar, /readiness, /model/info, /insights/washout."""

from __future__ import annotations

import json
from datetime import date, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.main import app
from core import openmeteo, readiness
from core.forecast import (
    EVAL_SUMMARY_PATH,
    LOW_EVIDENCE_PRIOR,
    display_probability,
)
from core.similar import WEATHER_SCALES, context_vector, vector_literal
from core.taxonomy import EQUIPMENT, GEOTECHNICAL, INCORRECT_OPERATION, MODEL_TARGETS
from scripts import load_postgres

EDSON = (53.58, -116.44)
REF = date(2024, 6, 1)
MEDIANS = dict.fromkeys(WEATHER_SCALES, 0.0)


def _incident(
    conn,
    number,
    when,
    lat,
    lon,
    hazard,
    *,
    site=0,
    operator="NGTL",
    commodity="gas",
    alberta=True,
    precip=None,
) -> None:
    conn.execute(
        "INSERT INTO incidents (incident_number, event_date, event_date_source, province, "
        "is_alberta, company, operator_group, commodity, latitude, longitude, geom, site_id, "
        "hazard_group, hazard_groups, is_model_target, raw, closed_date) VALUES "
        "(%s, %s, 'occurred', %s, %s, 'X', %s, %s, %s, %s, "
        "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s, %s, '{}', %s)",
        (
            number,
            when,
            "Alberta" if alberta else "British Columbia",
            alberta,
            operator,
            commodity,
            lat,
            lon,
            lon,
            lat,
            site,
            hazard,
            [hazard],
            hazard in MODEL_TARGETS,
            when + timedelta(days=30),
        ),
    )
    vec, _ = context_vector(lat, lon, when, None, commodity, MEDIANS)
    conn.execute(
        "INSERT INTO incident_context VALUES (%s, %s::vector, false)",
        (number, vector_literal(vec)),
    )
    if precip is not None:
        conn.execute(
            "INSERT INTO incident_weather (incident_number, precip_30d) VALUES (%s, %s)",
            (number, precip),
        )


@pytest.fixture
def api(pg_env: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    with psycopg.connect(pg_env, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(
            "TRUNCATE incidents, incident_context, incident_weather, pipelines, "
            "corridors, similarity_meta, crew_types, hazard_crew_map, crew_bases CASCADE"
        )
        conn.execute(
            "INSERT INTO similarity_meta (id, medians, scales) VALUES (1, %s, %s)",
            (json.dumps(MEDIANS), json.dumps(WEATHER_SCALES)),
        )
        conn.execute(
            "INSERT INTO pipelines (pipeline_name, company, commodity, geom) VALUES "
            "('Trans Mountain Pipeline', 'Trans Mountain Pipeline ULC', 'liquid', "
            "ST_Multi(ST_GeomFromText('LINESTRING(-116.6 53.57, -116.3 53.57)', 4326))::geography)"
        )
        conn.execute(
            "INSERT INTO corridors VALUES ('Edson', 5, %s, %s, "
            "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)",
            (EDSON[0], EDSON[1], EDSON[1], EDSON[0]),
        )
        # Edson: 4 earlier NGTL incidents at 2 sites; one later incident must be ignored.
        for i, (days, hz, site) in enumerate(
            [
                (-900, EQUIPMENT, 1),
                (-600, EQUIPMENT, 1),
                (-400, INCORRECT_OPERATION, 2),
                (-200, GEOTECHNICAL, 2),
            ]
        ):
            _incident(
                conn,
                f"E{i}",
                REF + timedelta(days=days),
                EDSON[0] + i * 0.01,
                EDSON[1],
                hz,
                site=site,
            )
        _incident(conn, "LATER", REF + timedelta(days=10), *EDSON, GEOTECHNICAL, site=1)
        load_postgres.seed_crews(conn)
        conn.commit()
    monkeypatch.setattr(
        readiness,
        "route",
        lambda a, b: {
            "provider": "fake",
            "duration_min": 42.0,
            "distance_km": 50.0,
            "geometry": None,
            "last_mile": None,
            "warning": None,
            "fallbacks": [],
        },
    )
    with TestClient(app) as client:
        yield client


def test_forecast_shape_and_rules(api: TestClient) -> None:
    body = api.post(
        "/forecast",
        json={"latitude": EDSON[0], "longitude": EDSON[1], "date": REF.isoformat()},
    ).json()
    probs = [h["probability"] for h in body["hazards"]]
    assert len(probs) == len(MODEL_TARGETS) and abs(sum(probs) - 1) < 1e-3
    assert probs == sorted(probs, reverse=True)
    assert body["evidence"]["prior_incidents"] == 4  # LATER is after the date
    assert body["low_evidence"] is False
    assert body["weather_in_model"] is False
    assert all(h["drivers"] for h in body["hazards"][:3])
    assert all(
        isinstance(d["text"], str) and d["effect"] in {"raises", "lowers"}
        for d in body["hazards"][0]["drivers"]
    )
    third = next(
        h for h in body["hazards"] if h["hazard_group"] == "third_party_damage"
    )
    assert third["low_evidence_group"] is True


def test_operator_defaults_to_nearby_history_not_nearest_line(api: TestClient) -> None:
    ctx = api.post(
        "/forecast",
        json={"latitude": EDSON[0], "longitude": EDSON[1], "date": REF.isoformat()},
    ).json()["context"]
    assert ctx["nearest_system"] == "Trans Mountain Pipeline"
    assert ctx["operator_group"] == "NGTL" and ctx["commodity"] == "gas"
    options = {o["operator_group"] for o in ctx["operator_options"]}
    assert {"NGTL", "Trans Mountain"} <= options
    chosen = api.post(
        "/forecast",
        json={
            "latitude": EDSON[0],
            "longitude": EDSON[1],
            "date": REF.isoformat(),
            "operator_group": "Trans Mountain",
        },
    ).json()["context"]
    assert (
        chosen["operator_group"] == "Trans Mountain" and chosen["commodity"] == "liquid"
    )
    assert chosen["operator_source"] == "chosen by user"


def test_low_evidence_far_from_history(api: TestClient) -> None:
    body = api.post(
        "/forecast",
        json={"latitude": 57.5, "longitude": -112.0, "date": REF.isoformat()},
    ).json()
    assert body["evidence"]["prior_incidents"] < LOW_EVIDENCE_PRIOR
    assert body["low_evidence"] is True
    assert body["context"]["operator_source"] == "nearest mapped CER pipeline system"


def test_forecast_by_corridor_and_validation(api: TestClient) -> None:
    r = api.post("/forecast", json={"corridor": "edson", "date": REF.isoformat()})
    assert r.status_code == 200 and r.json()["corridor"] == "edson"
    assert api.post("/forecast", json={"corridor": "Atlantis"}).status_code == 404
    assert api.post("/forecast", json={"date": REF.isoformat()}).status_code == 422


@pytest.mark.parametrize(
    ("p", "display", "lower"),
    [
        (0.07, "7%", False),
        (0.5, "50%", False),
        (0.51, ">50%, lower certainty", True),
    ],
)
def test_display_probability(p: float, display: str, lower: bool) -> None:
    assert display_probability(p) == {"display": display, "lower_certainty": lower}


def test_similar_endpoint(api: TestClient) -> None:
    body = api.get(
        "/similar",
        params={"lat": EDSON[0], "lon": EDSON[1], "date": REF.isoformat(), "k": 10},
    ).json()
    ids = [r["incident_number"] for r in body["incidents"]]
    assert ids and "LATER" not in ids
    assert api.get("/similar", params={"incident_id": "NOPE"}).status_code == 404
    assert api.get("/similar", params={"lat": 53.0}).status_code == 422


def fake_days(today: date) -> list[dict]:
    days = []
    for k in range(-30, 7):
        d = today + timedelta(days=k)
        days.append(
            {
                "date": d.isoformat(),
                "temperature_2m_max": 3.0 if k % 2 else -4.0,
                "temperature_2m_min": -5.0,
                "temperature_2m_mean": -1.0,
                "precipitation_sum": 1.0,
                "snowfall_sum": 0.5,
                "snow_depth_max": 0.12 if k == 0 else 0.1,
            }
        )
    return days


def test_open_meteo_summary() -> None:
    today = date(2026, 1, 10)
    s = openmeteo.summarize(fake_days(today), today)
    assert len(s["next_7_days"]) == 7
    assert s["prior_30_days"]["precip_mm"] == 30.0
    assert s["prior_30_days"]["freeze_thaw_days"] == 15  # odd offsets cross 0 °C
    assert s["similarity_weather"]["snow_on_ground_d0"] == 12.0  # metres -> cm
    assert s["outlook"]["precip_total_mm"] == 7.0


def test_readiness_with_weather(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        readiness.openmeteo, "fetch_daily", lambda la, lo, d: fake_days(d)
    )
    body = api.get(
        "/readiness", params={"corridor": "Edson", "start": REF.isoformat()}
    ).json()
    assert body["week"]["start"] == REF.isoformat()
    assert (
        body["weather"]["source"].startswith("Open-Meteo")
        and body["weather_note"] is None
    )
    assert body["weather_in_model"] is False
    assert 1 <= len(body["recommended"]) <= 3
    crew = body["recommended"][0]["crews"][0]
    assert crew["nearest_base"]["duration_min"] == 42.0
    assert body["sample_label"] == "Sample — to be validated"
    assert all(r["incident_number"] != "LATER" for r in body["similar"]["incidents"])


def test_readiness_offline_weather(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def offline(*_a):
        raise openmeteo.WeatherUnavailable("ConnectError")

    monkeypatch.setattr(readiness.openmeteo, "fetch_daily", offline)
    body = api.get(
        "/readiness",
        params={"lat": EDSON[0], "lon": EDSON[1], "start": REF.isoformat()},
    ).json()
    assert body["weather"] is None and "unavailable" in body["weather_note"]
    assert body["recommended"]  # forecast and crews still work offline


def test_model_info_matches_evaluation_summary(api: TestClient) -> None:
    body = api.get("/model/info").json()
    saved = json.loads(EVAL_SUMMARY_PATH.read_text())
    assert body["canada"] == saved["canada"] and body["alberta"] == saved["alberta"]
    assert body["features"]["weather_in_model"] is False
    assert {"canada", "alberta", "weather", "calibration"} <= set(body["plain_words"])


def test_washout_insight_is_computed_and_labelled(api: TestClient, pg_env: str) -> None:
    with psycopg.connect(pg_env) as conn:
        conn.execute("TRUNCATE incidents CASCADE")
        rows = [
            ("B1", 2019, EQUIPMENT, 10.0),
            ("B2", 2020, EQUIPMENT, 20.0),
            ("B3", 2021, GEOTECHNICAL, 30.0),
            ("B4", 2018, EQUIPMENT, 40.0),
            ("A1", 2023, GEOTECHNICAL, 50.0),
            ("A2", 2023, GEOTECHNICAL, 70.0),
            ("A3", 2024, EQUIPMENT, 5.0),
            ("X1", 2023, GEOTECHNICAL, 99.0),
        ]
        for n, year, hz, precip in rows:
            _incident(
                conn,
                n,
                date(year, 5, 1),
                *EDSON,
                hz,
                precip=precip,
                alberta=not n.startswith("X"),
            )
        conn.commit()
    body = api.get("/insights/washout").json()
    assert body["before"]["geotechnical_share"] == 0.25
    assert body["after"]["geotechnical_share"] == round(2 / 3, 3)
    assert body["after"]["median_precip_30d_geotechnical_mm"] == 60.0
    assert body["after"]["n_geotechnical_with_precip"] == 2
    assert body["is_forecast"] is False and "not a model forecast" in body["note"]
    assert "25.0% to 66.7%" in body["headline"]
