"""Similar-incident evidence (structured context) and the narrative pilot path."""

from __future__ import annotations

import json
import math
from datetime import date, timedelta

import psycopg
import pytest

from core import narratives
from core.similar import (
    GEO_SCALE_KM,
    VECTOR_DIM,
    WEATHER_SCALES,
    cause_summary,
    context_vector,
    find_similar,
    similar_to_incident,
    similarity_from_distance,
    vector_literal,
)

MEDIANS = dict.fromkeys(WEATHER_SCALES, 0.0)
EDSON = (53.58, -116.44)
REF = date(2024, 1, 15)


def dist(a: list[float], b: list[float]) -> float:
    return math.dist(a, b)


def test_vector_dimension_matches_schema() -> None:
    vec, _ = context_vector(*EDSON, REF, None, "gas", MEDIANS)
    assert len(vec) == VECTOR_DIM == 11


def test_geo_scale_one_unit_per_100_km() -> None:
    a, _ = context_vector(53.0, -116.0, REF, None, None, MEDIANS)
    b, _ = context_vector(53.0 + GEO_SCALE_KM / 111.2, -116.0, REF, None, None, MEDIANS)
    assert dist(a[:3], b[:3]) == pytest.approx(1.0, abs=0.01)


def test_season_scale_one_unit_per_30_days_and_wraps_new_year() -> None:
    a, _ = context_vector(*EDSON, date(2024, 1, 10), None, None, MEDIANS)
    b, _ = context_vector(*EDSON, date(2024, 2, 9), None, None, MEDIANS)
    c, _ = context_vector(*EDSON, date(2023, 12, 11), None, None, MEDIANS)
    assert dist(a[3:5], b[3:5]) == pytest.approx(1.0, abs=0.02)
    assert dist(a[3:5], c[3:5]) == pytest.approx(1.0, abs=0.02)  # across Dec -> Jan


def test_missing_weather_uses_fallback_and_is_flagged() -> None:
    fallback = {k: 5.0 for k in WEATHER_SCALES}
    vec, known = context_vector(*EDSON, REF, {"temp_mean_7d": -20.0}, "gas", fallback)
    assert known is False
    vec_full, known_full = context_vector(
        *EDSON, REF, {k: 5.0 for k in WEATHER_SCALES}, "gas", fallback
    )
    assert known_full is True
    assert vec[6:9] == vec_full[6:9]  # the three missing values took the fallback


def test_similarity_is_monotonic_in_distance() -> None:
    assert similarity_from_distance(0.0) == 1.0
    assert similarity_from_distance(1.0) > similarity_from_distance(2.0)


def test_cause_summary_plain_english() -> None:
    text = cause_summary(
        "Damage or deterioration mechanism, Equipment, Valve Seals or Packing;"
        "Substandard Acts, Failure to check or monitor",
        "Job or system factors, Inadequate maintenance, Excessive Wear",
    )
    assert text.startswith("What happened: Equipment — valve seals or packing")
    assert "Why: Inadequate maintenance — excessive wear." in text
    assert cause_summary(None, None) == "Cause codes not recorded."
    assert len(cause_summary("A, B, " + "x" * 400, None)) <= 220


# ----------------------------------------------------------------- database tests


def _insert_incident(
    conn: psycopg.Connection,
    number: str,
    when: date,
    lat: float,
    lon: float,
    hazard: str,
) -> None:
    conn.execute(
        "INSERT INTO incidents (incident_number, event_date, event_date_source, province, "
        "is_alberta, company, operator_group, commodity, latitude, longitude, geom, site_id, "
        "hazard_group, hazard_groups, is_model_target, raw) VALUES (%s, %s, 'occurred', "
        "'Alberta', true, 'X', 'X', 'gas', %s, %s, "
        "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 0, %s, %s, true, '{}')",
        (number, when, lat, lon, lon, lat, hazard, [hazard]),
    )
    vec, _ = context_vector(lat, lon, when, None, "gas", MEDIANS)
    conn.execute(
        "INSERT INTO incident_context VALUES (%s, %s::vector, false)",
        (number, vector_literal(vec)),
    )


@pytest.fixture
def seeded(pg_env: str):
    with psycopg.connect(pg_env, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(
            "TRUNCATE incidents, incident_context, incident_embeddings, similarity_meta CASCADE"
        )
        conn.execute(
            "INSERT INTO similarity_meta (id, medians, scales) VALUES (1, %s, %s)",
            (json.dumps(MEDIANS), json.dumps(WEATHER_SCALES)),
        )
        # Same place; dates straddle the reference date.
        for i, offset in enumerate((-400, -30, -1, 0, 1, 30)):
            _insert_incident(
                conn, f"T{i}", REF + timedelta(days=offset), *EDSON, "geotechnical"
            )
        _insert_incident(
            conn, "FAR", REF - timedelta(days=5), 49.0, -123.0, "fire_ignition"
        )
        conn.commit()
        yield conn


def test_forecast_search_only_returns_strictly_earlier(
    seeded: psycopg.Connection,
) -> None:
    out = find_similar(
        seeded, lat=EDSON[0], lon=EDSON[1], when=REF, commodity="gas", k=10
    )
    dates = [date.fromisoformat(r["date"]) for r in out["incidents"]]
    assert dates and all(d < REF for d in dates)
    assert {"T3", "T4", "T5"}.isdisjoint(
        {r["incident_number"] for r in out["incidents"]}
    )


def test_nearest_context_ranks_first(seeded: psycopg.Connection) -> None:
    out = find_similar(
        seeded, lat=EDSON[0], lon=EDSON[1], when=REF, commodity="gas", k=10
    )
    ids = [r["incident_number"] for r in out["incidents"]]
    assert ids[0] == "T2"  # one day earlier, same place
    assert ids[-1] == "FAR"


def test_incident_seeded_search_excludes_self_and_later(
    seeded: psycopg.Connection,
) -> None:
    out = similar_to_incident(seeded, "T3", k=10)  # T3 is on REF
    ids = {r["incident_number"] for r in out["incidents"]}
    assert "T3" not in ids and ids.isdisjoint({"T4", "T5"})
    assert similar_to_incident(seeded, "NOPE")["error"]


def test_narrative_pilot_store_and_search_respects_date(
    seeded: psycopg.Connection,
) -> None:
    def fake_encoder(texts: list[str]) -> list[list[float]]:
        return [
            [
                1.0 if j == len(t) % narratives.EMBEDDING_DIM else 0.0
                for j in range(narratives.EMBEDDING_DIM)
            ]
            for t in texts
        ]

    texts = ["washout at creek crossing", "valve packing leak"]
    vecs = narratives.embed_in_batches(texts, fake_encoder)
    narratives.store_embeddings(
        seeded, [("T1", "pilot_what", vecs[0]), ("T4", "pilot_what", vecs[0])]
    )
    hits = narratives.search_narratives(seeded, vecs[0], before=REF)
    assert [h["incident_number"] for h in hits] == ["T1"]  # T4 is after REF
    assert hits[0]["similarity"] == pytest.approx(1.0)


def test_narrative_text_building() -> None:
    text, used = narratives.build_text(
        {"what": "  Leak\nat valve ", "why": "", "summary": "Seal worn."},
        ["what", "why", "summary"],
    )
    assert text == "Leak at valve Seal worn." and used == ["what", "summary"]


def test_embedding_dimension_is_enforced() -> None:
    with pytest.raises(ValueError):
        narratives.embed_in_batches(["x"], lambda texts: [[0.0] * 10 for _ in texts])
