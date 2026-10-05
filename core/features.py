"""Forecast features — only information available before the incident.

Allowed inputs (see docs/DATA_PROFILE.md §9 leakage check):
- location: lat/lon, province, distance to the nearest CER pipeline system
- context: operator group, commodity carried (CER systems layer)
- time: day of year
- weather: Phase 3 features (ECCC history, or Open-Meteo / overrides at inference)
- area history: incidents strictly before the reference date within AREA_RADIUS_KM.
  Their hazard mix only uses incidents whose cause was known by then
  (closed before the reference date), weighted so each site counts once.

Never features: the incident's own cause, narrative-like codes, outcome fields,
facility/pipe-attribute fields (filled conditional on the cause), or the
event-date source flag.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from core.geo import haversine_km
from core.sites import SITE_RADIUS_KM
from core.taxonomy import MODEL_TARGETS
from core.weather import FEATURE_NAMES as WEATHER_FEATURES

AREA_RADIUS_KM = 25.0

# Snow on ground is stored but not a model feature: many stations stop reporting it
# in summer, so its missingness tracks season and class (DATA_PROFILE §9, "caution"),
# and live Open-Meteo data always fills it (train/serve skew).
EXCLUDED_WEATHER: frozenset[str] = frozenset({"snow_on_ground_d0"})
MODEL_WEATHER_FEATURES: tuple[str, ...] = tuple(
    f for f in WEATHER_FEATURES if f not in EXCLUDED_WEATHER
)
EPOCH = date(1970, 1, 1)

CATEGORICAL_FEATURES: tuple[str, ...] = ("province", "operator_group", "commodity")
LOCATION_TIME_FEATURES: tuple[str, ...] = (
    "latitude",
    "longitude",
    "doy_sin",
    "doy_cos",
    "dist_pipeline_km",
)
AREA_FEATURES: tuple[str, ...] = (
    "ah_n_prior",
    "ah_n_sites",
    "ah_n_known",
    "ah_n_known_sites",
    "ah_same_site_n",
    "ah_days_since_last",
    *(f"ah_mix_{c}" for c in MODEL_TARGETS),
)
FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "location_time": LOCATION_TIME_FEATURES,
    "context": CATEGORICAL_FEATURES,
    "weather": MODEL_WEATHER_FEATURES,
    "area_history": AREA_FEATURES,
}
ALL_FEATURES: tuple[str, ...] = tuple(f for g in FEATURE_GROUPS.values() for f in g)

# Columns that must never reach the model (asserted in tests).
FORBIDDEN_COLUMNS: frozenset[str] = frozenset(
    {
        "hazard_group",
        "hazard_groups",
        "is_model_target",
        "incident_types",
        "what_category",
        "detailed_what",
        "why_category",
        "detailed_why",
        "raw",
        "closed_date",
        "event_date_source",
        "status",
        "incident_number",
        "site_id",
    }
)


def day_number(d: date | pd.Timestamp) -> int:
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return (d - EPOCH).days


@dataclass(frozen=True)
class History:
    """Past incidents as arrays for fast strictly-before queries."""

    lat: np.ndarray
    lon: np.ndarray
    day: np.ndarray  # event day number
    known_day: np.ndarray  # day the cause became known (closed); +inf if never
    site: np.ndarray
    cls: np.ndarray  # index into MODEL_TARGETS, -1 if not a forecast target

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> History:
        idx = {c: i for i, c in enumerate(MODEL_TARGETS)}
        closed = pd.to_datetime(df["closed_date"])
        known = np.where(
            closed.notna(),
            (closed - pd.Timestamp(EPOCH)).dt.days.fillna(0).to_numpy(),
            np.inf,
        )
        return cls(
            lat=df["latitude"].to_numpy(dtype=float),
            lon=df["longitude"].to_numpy(dtype=float),
            day=np.array([day_number(pd.Timestamp(d)) for d in df["event_date"]]),
            known_day=known.astype(float),
            site=df["site_id"].to_numpy(dtype=int),
            cls=df["hazard_group"].map(lambda g: idx.get(g, -1)).to_numpy(dtype=int),
        )


def area_history(hist: History, lat: float, lon: float, when: date) -> dict[str, float]:
    """Area-history features at (lat, lon) for reference date `when` (strictly before)."""
    t = day_number(when)
    d = haversine_km(lat, lon, hist.lat, hist.lon)
    prior = (hist.day < t) & (d <= AREA_RADIUS_KM)
    known = prior & (hist.known_day < t) & (hist.cls >= 0)
    out: dict[str, float] = {
        "ah_n_prior": float(prior.sum()),
        "ah_n_sites": float(len(np.unique(hist.site[prior]))),
        "ah_n_known": float(known.sum()),
        "ah_n_known_sites": float(len(np.unique(hist.site[known]))),
        "ah_same_site_n": float((prior & (d <= SITE_RADIUS_KM)).sum()),
        "ah_days_since_last": float(t - hist.day[prior].max())
        if prior.any()
        else math.nan,
    }
    out.update(site_weighted_mix(hist.site[known], hist.cls[known]))
    return out


def site_weighted_mix(sites: np.ndarray, classes: np.ndarray) -> dict[str, float]:
    """Hazard mix where each site contributes total weight 1 (NaN if no sites)."""
    k = len(MODEL_TARGETS)
    if len(sites) == 0:
        return {f"ah_mix_{c}": math.nan for c in MODEL_TARGETS}
    mix = np.zeros(k)
    for s in np.unique(sites):
        counts = np.bincount(classes[sites == s], minlength=k).astype(float)
        mix += counts / counts.sum()
    mix /= len(np.unique(sites))
    return {f"ah_mix_{c}": float(v) for c, v in zip(MODEL_TARGETS, mix, strict=True)}


def doy_features(when: date) -> dict[str, float]:
    angle = 2 * math.pi * (when.timetuple().tm_yday - 1) / 365.25
    return {"doy_sin": math.sin(angle), "doy_cos": math.cos(angle)}


def feature_row(
    hist: History,
    *,
    lat: float,
    lon: float,
    when: date,
    province: str | None,
    operator_group: str | None,
    commodity: str | None,
    dist_pipeline_km: float | None,
    weather: dict[str, float | None] | None,
) -> dict[str, object]:
    """One feature row for a location + date context (training or inference)."""
    row: dict[str, object] = {
        "latitude": lat,
        "longitude": lon,
        "dist_pipeline_km": math.nan if dist_pipeline_km is None else dist_pipeline_km,
        "province": province,
        "operator_group": operator_group,
        "commodity": commodity,
        **doy_features(when),
    }
    for name in WEATHER_FEATURES:
        value = (weather or {}).get(name)
        row[name] = math.nan if value is None else float(value)
    row.update(area_history(hist, lat, lon, when))
    return row


def training_frame(incidents: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Features (ALL_FEATURES) and labels for every model-target incident.

    `incidents` holds all incidents (history includes non-target classes) with
    weather columns joined. Each row's area history uses strictly earlier rows.
    """
    hist = History.from_frame(incidents)
    target = incidents[incidents["hazard_group"].isin(MODEL_TARGETS)]
    rows = [
        feature_row(
            hist,
            lat=float(r.latitude),
            lon=float(r.longitude),
            when=pd.Timestamp(r.event_date).date(),
            province=r.province,
            operator_group=r.operator_group,
            commodity=r.commodity,
            dist_pipeline_km=r.dist_pipeline_km,
            weather={n: getattr(r, n) for n in WEATHER_FEATURES},
        )
        for r in target.itertuples()
    ]
    X = pd.DataFrame(rows, index=target.index)[list(ALL_FEATURES)]
    return X, target["hazard_group"]
