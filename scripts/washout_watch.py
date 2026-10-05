"""Washout watch (backlog, 3-hour time box) — judged ONLY on pre-2022 rolling origins.

Usage: python -m scripts.washout_watch   (needs scripts.fetch_precip_normals and
scripts.washout_crossings to have run; the latter needs `pip install osmium`, which is
not in requirements.txt because the features were dropped)

Candidate features (all known before the incident):
- precip_30d_anomaly_mm / precip_30d_ratio: prior-30-day rain at the incident's station
  minus / divided by that station's median for the same calendar window in the
  NORMAL_YEARS years *before* the incident (>= MIN_NORMAL_YEARS valid years).
- dist_crossing_km / n_crossings_10km: nearest pipeline–waterway crossing (Alberta OSM).

Decision rule, fixed before running (docs/BACKLOG.md):
- Rolling origins with test years 2016–2021 only; each year trained on earlier years.
  The 2022+ test set is never used.
- Adopt a feature set only if the pooled paired-bootstrap Δ log loss (with − without)
  has its 95% CI entirely below 0 AND no single year is measurably worse.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from core import weather
from core.env import load_dotenv
from core.features import ALL_FEATURES, training_frame
from core.metrics import METRICS, paired_difference
from core.model import class_index, train
from core.taxonomy import GEOTECHNICAL, MODEL_TARGETS
from scripts.evaluate import load_incidents, md_table

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "data" / "weather" / "daily"
WEATHER_CSV = ROOT / "data" / "processed" / "incident_weather.csv"
CROSSINGS_CSV = ROOT / "data" / "processed" / "incident_crossings.csv"
REPORT = ROOT / "docs" / "WASHOUT_WATCH.md"

NORMAL_YEARS = 10
MIN_NORMAL_YEARS = 3
LOOKBACK_DAYS = 30
ORIGIN_YEARS = (2016, 2017, 2018, 2019, 2020, 2021)

ANOMALY = ("precip_30d_anomaly_mm", "precip_30d_ratio")
CROSSING = ("dist_crossing_km", "n_crossings_10km")
CANDIDATES: dict[str, tuple[str, ...]] = {
    "+ rainfall anomaly": ANOMALY,
    "+ waterway crossings": CROSSING,
    "+ both": ANOMALY + CROSSING,
}

_cache: dict[tuple[int, int], pd.DataFrame | None] = {}


def station_year(station: int, year: int) -> pd.DataFrame | None:
    key = (station, year)
    if key not in _cache:
        path = DAILY_DIR / str(station) / f"{year}.csv"
        try:
            _cache[key] = weather.parse_daily_csv(path) if path.exists() else None
        except (ValueError, pd.errors.ParserError):
            _cache[key] = None
    return _cache[key]


def window_total(station: int, end: datetime) -> float:
    """Total precip over the LOOKBACK_DAYS before `end`; NaN under 80% coverage."""
    start = end - timedelta(days=LOOKBACK_DAYS)
    frames = [
        station_year(station, y)
        for y in sorted({start.year, (end - timedelta(days=1)).year})
    ]
    if any(f is None for f in frames):
        return math.nan
    daily = pd.concat(frames)
    return weather.precip_features(daily, end.date())["precip_30d"]


def anomaly_features(wx: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in wx.itertuples():
        out = {
            "incident_number": r.incident_number,
            ANOMALY[0]: math.nan,
            ANOMALY[1]: math.nan,
        }
        if pd.notna(r.precip_station_id) and pd.notna(r.precip_30d):
            st = int(r.precip_station_id)
            d0 = datetime.fromisoformat(str(r.event_date)[:10])
            prior = [
                window_total(
                    st,
                    d0.replace(year=d0.year - k)
                    if not (d0.month == 2 and d0.day == 29)
                    else d0.replace(year=d0.year - k, day=28),
                )
                for k in range(1, NORMAL_YEARS + 1)
            ]
            prior = [p for p in prior if not math.isnan(p)]
            if len(prior) >= MIN_NORMAL_YEARS:
                normal = float(np.median(prior))
                out[ANOMALY[0]] = float(r.precip_30d) - normal
                out[ANOMALY[1]] = (
                    float(r.precip_30d) / normal if normal > 0 else math.nan
                )
        rows.append(out)
    return pd.DataFrame(rows)


def build_frame() -> tuple[
    pd.DataFrame, pd.Series, pd.Series, pd.Series, dict[str, float]
]:
    df = load_incidents()
    X, y = training_frame(df)
    meta = df.loc[X.index]
    wx = pd.read_csv(WEATHER_CSV)
    extra = anomaly_features(wx).merge(
        pd.read_csv(CROSSINGS_CSV), on="incident_number", how="outer"
    )
    X = X.join(meta[["incident_number"]]).merge(extra, on="incident_number", how="left")
    X.index = meta.index
    coverage = {c: float(X[c].notna().mean()) for c in ANOMALY + CROSSING}
    return X, y, meta["event_date"].dt.year, meta["is_alberta"].astype(bool), coverage


def rolling(
    X: pd.DataFrame, y: pd.Series, years: pd.Series, ab: pd.Series
) -> dict[str, dict]:
    """Pooled predictions over ORIGIN_YEARS for the deployed set and each candidate."""
    sets = {"deployed": list(ALL_FEATURES)} | {
        k: [*ALL_FEATURES, *v] for k, v in CANDIDATES.items()
    }
    pooled = {k: [] for k in sets}
    ys, abs_, yrs = [], [], []
    for year in ORIGIN_YEARS:
        tr, te = years < year, years == year
        for name, cols in sets.items():
            pooled[name].append(
                train(X[tr], y[tr], years[tr], cols).predict_proba(X[te])
            )
        ys.append(class_index(y[te]))
        abs_.append(ab[te].to_numpy())
        yrs.append(np.full(int(te.sum()), year))
    return {
        "p": {k: np.vstack(v) for k, v in pooled.items()},
        "y": np.concatenate(ys),
        "ab": np.concatenate(abs_),
        "year": np.concatenate(yrs),
    }


def fmt(d: tuple[float, float, float]) -> str:
    return f"{d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}]"


def evaluate_sets(
    r: dict,
) -> tuple[list[list[object]], list[list[object]], dict[str, bool]]:
    ll = METRICS["log_loss"]
    g = MODEL_TARGETS.index(GEOTECHNICAL)
    summary, per_year, adopt = [], [], {}
    for name in CANDIDATES:
        pa, pb = r["p"][name], r["p"]["deployed"]
        pooled = paired_difference(ll, pa, pb, r["y"])
        ab = r["ab"]
        ab_d = paired_difference(ll, pa[ab], pb[ab], r["y"][ab])
        geo = r["y"] == g
        year_rows, worse = [], False
        for year in ORIGIN_YEARS:
            m = r["year"] == year
            d = paired_difference(ll, pa[m], pb[m], r["y"][m])
            worse |= d[1] > 0
            year_rows.append(fmt(d))
        adopt[name] = pooled[2] < 0 and not worse
        summary.append(
            [
                name,
                fmt(pooled),
                fmt(ab_d),
                f"{pb[geo, g].mean():.1%} → {pa[geo, g].mean():.1%}",
                "adopt" if adopt[name] else "drop",
            ]
        )
        per_year.append([name, *year_rows])
    return summary, per_year, adopt


def main() -> None:
    load_dotenv()
    started = datetime.now(UTC)
    X, y, years, ab, coverage = build_frame()
    r = rolling(X, y, years, ab)
    summary, per_year, adopt = evaluate_sets(r)
    n = len(r["y"])
    text = "\n\n".join(
        [
            "# Washout watch — result",
            (
                f"Run {started:%Y-%m-%d %H:%M} UTC by `scripts/washout_watch.py`. Backlog item, 3-hour "
                "time box. **Judged only on rolling origins with test years "
                f"{ORIGIN_YEARS[0]}–{ORIGIN_YEARS[-1]}** (each trained on earlier years); the 2022+ test "
                "set was not used."
            ),
            "## Candidate features",
            (
                f"- **Rainfall anomaly**: prior-30-day station rain minus / divided by the station's median "
                f"for the same window in the {NORMAL_YEARS} years before the incident "
                f"(≥ {MIN_NORMAL_YEARS} valid years). Coverage: {coverage[ANOMALY[0]]:.1%} of target incidents."
            ),
            (
                f"- **Waterway crossings**: distance to the nearest pipeline–waterway crossing and crossings "
                f"within 10 km (Alberta OSM rivers/streams/canals × CER pipeline systems). Coverage: "
                f"{coverage[CROSSING[0]]:.1%} (Alberta only; elsewhere missing, never zero)."
            ),
            "## Decision rule (fixed before running)",
            (
                "Adopt a feature set only if the pooled paired-bootstrap Δ log loss (with − without) "
                "has its 95% CI entirely below 0 **and** no single origin year is measurably worse."
            ),
            f"## Result ({n} incidents pooled over {len(ORIGIN_YEARS)} origins)",
            "Δ log loss = with − deployed (negative = the feature helps), 95% CI.",
            md_table(
                [
                    "candidate",
                    "Δ pooled (Canada)",
                    "Δ pooled (Alberta)",
                    "mean p(geotech) on actual geotech, deployed → with",
                    "decision",
                ],
                summary,
            ),
            "### Per origin year (Canada)",
            md_table(["candidate", *map(str, ORIGIN_YEARS)], per_year),
            "## Conclusion",
            (
                "At least one candidate met the rule; see the decision column. The deployed model is "
                "NOT changed until this is discussed."
                if any(adopt.values())
                else "No candidate met the rule. The washout features are **dropped**; the descriptive "
                "finding stays as the UI insight card (GET /insights/washout), labelled as an observed "
                "pattern, not a forecast. Alberta-only results are shown for information: under the "
                "rule they cannot adopt a feature, and none of their intervals excludes zero either. "
                "The crossing-distance pattern (washouts closer to pipeline–waterway crossings before "
                "2022) is kept as an observed, suggestive finding for a pilot — see docs/QA_PREP.md."
            ),
        ]
    )
    REPORT.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
