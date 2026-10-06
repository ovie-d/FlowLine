"""Daily-weather features for an incident date (Environment Canada daily data).

Windows (d0 = event day):
- day-of: d0
- prior 7 / 30 days: d0-7 … d0-1 and d0-30 … d0-1 (the event day is excluded)

A window statistic is NaN — never zero — when fewer than MIN_COVERAGE of its days
have data. Precipitation totals are raw sums over the observed days.
"""

from __future__ import annotations

import io
import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

MIN_COVERAGE = 0.8
SNOW_LOOKBACK_DAYS = 3

# ECCC bulk CSV column -> our name.
DAILY_COLUMNS: dict[str, str] = {
    "Date/Time": "date",
    "Max Temp (°C)": "t_max",
    "Min Temp (°C)": "t_min",
    "Mean Temp (°C)": "t_mean",
    "Total Precip (mm)": "precip",
    "Snow on Grnd (cm)": "snow_ground",
}

FEATURE_NAMES: tuple[str, ...] = (
    "temp_mean_d0",
    "temp_min_d0",
    "temp_max_d0",
    "temp_mean_7d",
    "temp_min_7d",
    "temp_max_7d",
    "temp_mean_30d",
    "temp_min_30d",
    "temp_max_30d",
    "freeze_thaw_30d",
    "precip_7d",
    "precip_30d",
    "snow_on_ground_d0",
)


def parse_daily_csv(source: str | Path) -> pd.DataFrame:
    """ECCC bulk daily CSV (path or text) -> frame indexed by date."""
    text = (
        Path(source).read_text(encoding="utf-8-sig")
        if isinstance(source, Path)
        else source
    )
    raw = pd.read_csv(io.StringIO(text), usecols=lambda c: c in DAILY_COLUMNS)
    df = raw.rename(columns=DAILY_COLUMNS)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def window(daily: pd.DataFrame, d0: date, days: int) -> pd.DataFrame:
    """Rows for d0-days … d0-1, reindexed so missing days are NaN rows."""
    idx = [d0 - timedelta(days=k) for k in range(days, 0, -1)]
    return daily.reindex(idx)


def coverage(frame: pd.DataFrame, col: str) -> float:
    if col not in frame or len(frame) == 0:
        return 0.0
    return float(frame[col].notna().mean())


def _stat(frame: pd.DataFrame, col: str, how: str) -> float:
    if coverage(frame, col) < MIN_COVERAGE:
        return math.nan
    return float(getattr(frame[col], how)())


def _day(daily: pd.DataFrame, d0: date, col: str) -> float:
    if d0 not in daily.index or col not in daily:
        return math.nan
    value = daily.at[d0, col]
    return float(value) if pd.notna(value) else math.nan


def freeze_thaw_days(frame: pd.DataFrame) -> float:
    """Days whose max is above 0 °C and min below 0 °C (crossing freezing)."""
    both = frame[["t_max", "t_min"]].dropna()
    if len(frame) == 0 or len(both) / len(frame) < MIN_COVERAGE:
        return math.nan
    return float(((both["t_max"] > 0) & (both["t_min"] < 0)).sum())


def temperature_features(daily: pd.DataFrame, d0: date) -> dict[str, float]:
    w7, w30 = window(daily, d0, 7), window(daily, d0, 30)
    return {
        "temp_mean_d0": _day(daily, d0, "t_mean"),
        "temp_min_d0": _day(daily, d0, "t_min"),
        "temp_max_d0": _day(daily, d0, "t_max"),
        "temp_mean_7d": _stat(w7, "t_mean", "mean"),
        "temp_min_7d": _stat(w7, "t_min", "min"),
        "temp_max_7d": _stat(w7, "t_max", "max"),
        "temp_mean_30d": _stat(w30, "t_mean", "mean"),
        "temp_min_30d": _stat(w30, "t_min", "min"),
        "temp_max_30d": _stat(w30, "t_max", "max"),
        "freeze_thaw_30d": freeze_thaw_days(w30),
    }


def precip_features(daily: pd.DataFrame, d0: date) -> dict[str, float]:
    return {
        "precip_7d": _stat(window(daily, d0, 7), "precip", "sum"),
        "precip_30d": _stat(window(daily, d0, 30), "precip", "sum"),
    }


def snow_features(daily: pd.DataFrame, d0: date) -> dict[str, float]:
    """Snow on ground on d0, else the most recent value in the prior few days."""
    for k in range(SNOW_LOOKBACK_DAYS + 1):
        value = _day(daily, d0 - timedelta(days=k), "snow_ground")
        if not math.isnan(value):
            return {"snow_on_ground_d0": value}
    return {"snow_on_ground_d0": math.nan}


# Station-suitability tests per variable group (used to pick the nearest usable station).
def has_temperature(daily: pd.DataFrame, d0: date) -> bool:
    return coverage(window(daily, d0, 30), "t_mean") >= MIN_COVERAGE


def has_precip(daily: pd.DataFrame, d0: date) -> bool:
    return coverage(window(daily, d0, 30), "precip") >= MIN_COVERAGE


def has_snow(daily: pd.DataFrame, d0: date) -> bool:
    return not math.isnan(snow_features(daily, d0)["snow_on_ground_d0"])
