"""Leakage guards for forecast features, plus model and metric sanity checks."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from core import metrics
from core.features import (
    ALL_FEATURES,
    FORBIDDEN_COLUMNS,
    History,
    area_history,
    site_weighted_mix,
    training_frame,
)
from core.model import HazardModel, train
from core.taxonomy import (
    CORROSION_CRACKING,
    EQUIPMENT,
    GEOTECHNICAL,
    MODEL_TARGETS,
    OTHER,
)
from core.weather import FEATURE_NAMES as WEATHER_FEATURES

T = date(2022, 6, 1)
HERE = (53.58, -116.44)


def frame(rows: list[dict]) -> pd.DataFrame:
    base = {
        "province": "Alberta",
        "operator_group": "NGTL",
        "commodity": "gas",
        "dist_pipeline_km": 1.0,
        "is_alberta": True,
        **dict.fromkeys(WEATHER_FEATURES, np.nan),
    }
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["event_date"] = pd.to_datetime(df["event_date"])
    df["closed_date"] = pd.to_datetime(df["closed_date"])
    return df


def inc(
    days: int,
    hazard: str,
    site: int = 0,
    closed_after: int | None = 10,
    lat: float = HERE[0],
    lon: float = HERE[1],
) -> dict:
    when = T + timedelta(days=days)
    closed = None if closed_after is None else when + timedelta(days=closed_after)
    return {
        "event_date": when,
        "closed_date": closed,
        "hazard_group": hazard,
        "site_id": site,
        "latitude": lat,
        "longitude": lon,
    }


def test_no_forbidden_column_is_a_feature() -> None:
    assert FORBIDDEN_COLUMNS.isdisjoint(ALL_FEATURES)
    assert not any(c.startswith(("detailed_", "raw")) for c in ALL_FEATURES)


def test_future_incidents_do_not_change_features() -> None:
    past = [inc(-300, EQUIPMENT), inc(-200, GEOTECHNICAL, site=1), inc(-100, EQUIPMENT)]
    future = [
        inc(0, CORROSION_CRACKING, site=2),
        inc(5, GEOTECHNICAL),
        inc(90, EQUIPMENT),
    ]
    with_future = area_history(History.from_frame(frame(past + future)), *HERE, T)
    without = area_history(History.from_frame(frame(past)), *HERE, T)
    assert with_future == pytest.approx(without, nan_ok=True)


def test_same_day_incident_is_excluded() -> None:
    feats = area_history(History.from_frame(frame([inc(0, EQUIPMENT)])), *HERE, T)
    assert feats["ah_n_prior"] == 0 and math.isnan(feats["ah_days_since_last"])


def test_cause_not_used_until_incident_is_closed() -> None:
    # Happened before T but closed after T: counts as an incident, not in the mix.
    feats = area_history(
        History.from_frame(frame([inc(-5, GEOTECHNICAL, closed_after=30)])), *HERE, T
    )
    assert feats["ah_n_prior"] == 1 and feats["ah_n_known"] == 0
    assert math.isnan(feats[f"ah_mix_{GEOTECHNICAL}"])
    never = area_history(
        History.from_frame(frame([inc(-500, GEOTECHNICAL, closed_after=None)])),
        *HERE,
        T,
    )
    assert never["ah_n_known"] == 0


def test_busy_site_counts_once_in_mix() -> None:
    sites = np.array([0] * 10 + [1])
    classes = np.array(
        [MODEL_TARGETS.index(EQUIPMENT)] * 10 + [MODEL_TARGETS.index(GEOTECHNICAL)]
    )
    mix = site_weighted_mix(sites, classes)
    assert mix[f"ah_mix_{EQUIPMENT}"] == pytest.approx(0.5)
    assert mix[f"ah_mix_{GEOTECHNICAL}"] == pytest.approx(0.5)


def test_far_incidents_are_outside_the_area() -> None:
    far = inc(-100, EQUIPMENT, lat=49.0, lon=-123.0)
    feats = area_history(History.from_frame(frame([far])), *HERE, T)
    assert feats["ah_n_prior"] == 0


def test_own_label_never_reaches_own_features() -> None:
    rows = [
        inc(-400, EQUIPMENT, site=1),
        inc(-50, GEOTECHNICAL, site=2),
        inc(0, EQUIPMENT),
    ]
    X1, _ = training_frame(frame(rows))
    rows[-1]["hazard_group"] = CORROSION_CRACKING
    X2, _ = training_frame(frame(rows))
    pd.testing.assert_frame_equal(X1, X2)


def test_non_target_classes_are_history_but_not_rows() -> None:
    rows = [inc(-400, OTHER, site=1), inc(0, EQUIPMENT)]
    X, y = training_frame(frame(rows))
    assert list(y) == [EQUIPMENT]
    assert X.iloc[0]["ah_n_prior"] == 1 and X.iloc[0]["ah_n_known"] == 0


# ------------------------------------------------------------------ model


@pytest.fixture(scope="module")
def tiny_model() -> tuple[HazardModel, pd.DataFrame]:
    rng = np.random.default_rng(0)
    n = 400
    X = pd.DataFrame(
        {
            "latitude": rng.uniform(49, 60, n),
            "longitude": rng.uniform(-120, -110, n),
            "province": rng.choice(["Alberta", "British Columbia"], n),
        }
    )
    y = pd.Series(np.where(X["latitude"] > 55, GEOTECHNICAL, EQUIPMENT))
    y.iloc[:40] = CORROSION_CRACKING
    years = pd.Series(rng.integers(2015, 2022, n))
    return train(X, y, years, ["latitude", "longitude", "province"]), X


def test_model_probabilities_are_valid(
    tiny_model: tuple[HazardModel, pd.DataFrame],
) -> None:
    model, X = tiny_model
    p = model.predict_proba(X)
    assert p.shape == (len(X), len(MODEL_TARGETS))
    assert np.allclose(p.sum(axis=1), 1.0) and (p >= 0).all()
    g = MODEL_TARGETS.index(GEOTECHNICAL)
    assert p[X["latitude"] > 57, g].mean() > p[X["latitude"] < 52, g].mean()


def test_model_save_load_round_trip(tmp_path, tiny_model) -> None:
    model, X = tiny_model
    model.save(tmp_path / "m")
    loaded = HazardModel.load(tmp_path / "m")
    assert np.allclose(loaded.predict_proba(X), model.predict_proba(X))


def test_shap_shape(tiny_model) -> None:
    model, X = tiny_model
    assert model.shap_values(X.head(5)).shape == (5, len(MODEL_TARGETS), 4)


# ------------------------------------------------------------------ metrics


def test_metrics_on_known_values() -> None:
    p = np.array([[0.8, 0.2], [0.3, 0.7]])
    y = np.array([0, 1])
    assert metrics.log_loss(p, y) == pytest.approx(-(math.log(0.8) + math.log(0.7)) / 2)
    assert metrics.brier(p, y) == pytest.approx(((0.2**2) * 2 + (0.3**2) * 2) / 2)
    assert metrics.top1(p, y) == 1.0
    assert list(metrics.per_class_recall(p, y, 2)) == [1.0, 1.0]


def test_bootstrap_ci_brackets_point_and_identical_diff_is_zero() -> None:
    rng = np.random.default_rng(1)
    p = rng.dirichlet(np.ones(4), size=200)
    y = rng.integers(0, 4, 200)
    point, lo, hi = metrics.bootstrap(metrics.log_loss, p, y, n_boot=200)
    assert lo <= point <= hi
    assert metrics.paired_difference(metrics.log_loss, p, p, y, n_boot=50) == (
        0.0,
        0.0,
        0.0,
    )
