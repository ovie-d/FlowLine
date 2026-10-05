"""Weather feature calculation from ECCC daily data."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from core import weather
from core.geo import haversine_km

D0 = date(2020, 3, 31)


def make_daily(
    days: int = 40,
    t_max: float = 5.0,
    t_min: float = -5.0,
    precip: float | None = 1.0,
    snow: float | None = 10.0,
) -> pd.DataFrame:
    idx = [D0 - timedelta(days=k) for k in range(days, -1, -1)]
    return pd.DataFrame(
        {
            "t_max": t_max,
            "t_min": t_min,
            "t_mean": (t_max + t_min) / 2,
            "precip": precip,
            "snow_ground": snow,
        },
        index=idx,
        dtype=float,
    )


def test_prior_windows_exclude_event_day() -> None:
    daily = make_daily(precip=1.0)
    daily.loc[D0, "precip"] = 500.0  # must not count in prior windows
    out = weather.precip_features(daily, D0)
    assert out == {"precip_7d": 7.0, "precip_30d": 30.0}


def test_day_of_temperature() -> None:
    daily = make_daily()
    daily.loc[D0, ["t_max", "t_min", "t_mean"]] = [12.0, 2.0, 7.0]
    out = weather.temperature_features(daily, D0)
    assert (out["temp_max_d0"], out["temp_min_d0"], out["temp_mean_d0"]) == (
        12.0,
        2.0,
        7.0,
    )


def test_freeze_thaw_counts_days_crossing_zero() -> None:
    daily = make_daily(t_max=-2.0, t_min=-10.0)  # all frozen
    crossing = [D0 - timedelta(days=k) for k in (1, 5, 9)]
    daily.loc[crossing, "t_max"] = 3.0
    assert weather.freeze_thaw_days(weather.window(daily, D0, 30)) == 3.0


def test_low_coverage_gives_nan_not_zero() -> None:
    daily = make_daily(precip=None)
    daily.loc[D0 - timedelta(days=1), "precip"] = 4.0  # 1 of 30 days observed
    out = weather.precip_features(daily, D0)
    assert math.isnan(out["precip_7d"]) and math.isnan(out["precip_30d"])
    assert not weather.has_precip(daily, D0)


def test_missing_days_reduce_coverage() -> None:
    daily = make_daily().drop(index=[D0 - timedelta(days=k) for k in range(1, 8)])
    assert weather.coverage(weather.window(daily, D0, 30), "t_mean") == pytest.approx(
        23 / 30
    )
    assert weather.has_temperature(daily, D0) is False


def test_snow_falls_back_to_recent_day() -> None:
    daily = make_daily(snow=None)
    daily.loc[D0 - timedelta(days=2), "snow_ground"] = 15.0
    assert weather.snow_features(daily, D0) == {"snow_on_ground_d0": 15.0}
    daily.loc[D0 - timedelta(days=2), "snow_ground"] = math.nan
    assert math.isnan(weather.snow_features(daily, D0)["snow_on_ground_d0"])


def test_parse_eccc_bulk_csv() -> None:
    text = (
        '"Longitude (x)","Latitude (y)","Station Name","Climate ID","Date/Time","Year",'
        '"Month","Day","Data Quality","Max Temp (°C)","Max Temp Flag","Min Temp (°C)",'
        '"Min Temp Flag","Mean Temp (°C)","Mean Temp Flag","Total Precip (mm)",'
        '"Total Precip Flag","Snow on Grnd (cm)","Snow on Grnd Flag"\n'
        '"-113.52","53.57","X","1","2015-01-01","2015","01","01","","3.2","","-10.9","",'
        '"-3.9","","","M","12",""\n'
    )
    df = weather.parse_daily_csv(text)
    row = df.loc[date(2015, 1, 1)]
    assert row["t_max"] == 3.2 and row["snow_ground"] == 12.0
    assert math.isnan(row["precip"])


def test_feature_names_cover_all_groups() -> None:
    daily = make_daily()
    names = {
        **weather.temperature_features(daily, D0),
        **weather.precip_features(daily, D0),
        **weather.snow_features(daily, D0),
    }
    assert set(names) == set(weather.FEATURE_NAMES)


def test_haversine_edmonton_calgary() -> None:
    assert haversine_km(53.5461, -113.4938, 51.0447, -114.0719) == pytest.approx(
        281, abs=3
    )
