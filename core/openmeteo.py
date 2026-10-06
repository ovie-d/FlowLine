"""Upcoming and recent weather from Open-Meteo (free, no key) — context only.

Weather is NOT a forecast-model input (docs/MODEL_REPORT.md). It feeds the weather
context panel, the readiness briefing and the similar-incident search. When offline,
callers get WeatherUnavailable and show "weather unavailable" instead.
"""

from __future__ import annotations

import math
import time
from datetime import date
from typing import Any

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PAST_DAYS = 30
FORECAST_DAYS = 7
CACHE_TTL_S = 3600
TIMEOUT_S = 6.0
DAILY_VARS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "snowfall_sum",
    "snow_depth_max",
)
SOURCE = "Open-Meteo (open-meteo.com)"

_cache: dict[tuple[float, float, str], tuple[float, list[dict[str, Any]]]] = {}


class WeatherUnavailable(Exception):
    """Open-Meteo could not be reached or returned an unusable response."""


def fetch_daily(
    lat: float, lon: float, today: date, client: httpx.Client | None = None
) -> list[dict[str, Any]]:
    """PAST_DAYS before today + FORECAST_DAYS from today, one dict per day."""
    key = (round(lat, 2), round(lon, 2), today.isoformat())
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(DAILY_VARS),
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",
    }
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S)
    try:
        resp = client.get(FORECAST_URL, params=params)
        resp.raise_for_status()
        daily = resp.json()["daily"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise WeatherUnavailable(str(exc) or exc.__class__.__name__) from exc
    finally:
        if own:
            client.close()
    days = [
        {
            "date": daily["time"][i],
            **{v: daily.get(v, [None] * len(daily["time"]))[i] for v in DAILY_VARS},
        }
        for i in range(len(daily["time"]))
    ]
    _cache[key] = (time.monotonic(), days)
    return days


def _vals(days: list[dict[str, Any]], var: str) -> list[float]:
    return [float(d[var]) for d in days if d.get(var) is not None]


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def summarize(days: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Next-7-day outlook, prior-30-day context, and similarity-search weather."""
    iso = today.isoformat()
    past = [d for d in days if d["date"] < iso]
    ahead = [d for d in days if d["date"] >= iso][:FORECAST_DAYS]
    if len(ahead) < FORECAST_DAYS or len(past) < PAST_DAYS:
        # Open-Meteo's window is anchored on the real today: other weeks are not covered,
        # and partial windows would turn missing days into false zeros.
        raise WeatherUnavailable("weather outlook only covers the coming 7 days")
    last7 = past[-7:]
    freeze_thaw = sum(
        1
        for d in past
        if d["temperature_2m_max"] is not None
        and d["temperature_2m_min"] is not None
        and d["temperature_2m_max"] > 0 > d["temperature_2m_min"]
    )
    precip_past = _vals(past, "precipitation_sum")
    today_row = next((d for d in days if d["date"] == iso), None)
    snow_m = today_row.get("snow_depth_max") if today_row else None
    similarity = {
        "temp_mean_7d": _mean(_vals(last7, "temperature_2m_mean")),
        "precip_30d": round(sum(precip_past), 1) if precip_past else None,
        "freeze_thaw_30d": float(freeze_thaw) if past else None,
        "snow_on_ground_d0": None if snow_m is None else round(float(snow_m) * 100, 1),
    }
    lows, highs = _vals(ahead, "temperature_2m_min"), _vals(ahead, "temperature_2m_max")
    return {
        "source": SOURCE,
        "next_7_days": [
            {
                "date": d["date"],
                "t_min": d["temperature_2m_min"],
                "t_max": d["temperature_2m_max"],
                "precip_mm": d["precipitation_sum"],
                "snowfall_cm": d["snowfall_sum"],
            }
            for d in ahead
        ],
        "outlook": {
            "min_temp": min(lows) if lows else None,
            "max_temp": max(highs) if highs else None,
            "precip_total_mm": round(sum(_vals(ahead, "precipitation_sum")), 1),
            "snowfall_total_cm": round(sum(_vals(ahead, "snowfall_sum")), 1),
        },
        "prior_30_days": {
            "precip_mm": similarity["precip_30d"],
            "freeze_thaw_days": freeze_thaw if past else None,
            "mean_temp_last_7_days": similarity["temp_mean_7d"],
        },
        "similarity_weather": {
            k: v
            for k, v in similarity.items()
            if v is not None and not (isinstance(v, float) and math.isnan(v))
        },
    }
