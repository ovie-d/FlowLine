"""Match every CER incident to nearby ECCC daily weather and compute features.

Usage: python -m scripts.fetch_weather [--limit N]

Method (confirmed against ECCC "Get More Data" docs, 2026-10-05):
- Station inventory: Station Inventory EN.csv (collaboration.cmc.ec.gc.ca).
- Daily data: climate.weather.gc.ca/climate_data/bulk_data_e.html with
  timeframe=2 returns one station-year per request.

Per incident and per variable group (temperature, precipitation, snow on ground),
the nearest station whose daily data covers the window is used; distance is
recorded. Station-years are cached in data/weather/daily/ (resume = rerun).
Requests are throttled to >= 1 s apart.

Outputs: data/processed/incident_weather.csv, docs/WEATHER_COVERAGE.md
"""

from __future__ import annotations

import argparse
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from core import weather
from core.cer import load_cer
from core.geo import haversine_km

ROOT = Path(__file__).resolve().parent.parent
WEATHER_DIR = ROOT / "data" / "weather"
DAILY_DIR = WEATHER_DIR / "daily"
INVENTORY_PATH = WEATHER_DIR / "station_inventory_en.csv"
INVENTORY_URL = (
    "https://collaboration.cmc.ec.gc.ca/cmc/climate/Get_More_Data_Plus_de_donnees/"
    "Station%20Inventory%20EN.csv"
)
BULK_URL = "https://climate.weather.gc.ca/climate_data/bulk_data_e.html"
OUT_PATH = ROOT / "data" / "processed" / "incident_weather.csv"
REPORT_PATH = ROOT / "docs" / "WEATHER_COVERAGE.md"

PREFERRED_KM = 50.0
MAX_SEARCH_KM = 100.0
MAX_CANDIDATES = 6
LOOKBACK_DAYS = 30
MIN_REQUEST_GAP_S = 1.0
RETRY_WAITS_S = (5.0, 20.0, 60.0)
USER_AGENT = "FlowLine/1.0 (pipeline hazard research)"

GROUPS: dict[str, tuple[Callable, Callable]] = {
    "temp": (weather.has_temperature, weather.temperature_features),
    "precip": (weather.has_precip, weather.precip_features),
    "snow": (weather.has_snow, weather.snow_features),
}


class Downloader:
    """Throttled, cached ECCC bulk downloader (one station-year per file)."""

    def __init__(self) -> None:
        self._last = 0.0
        self._memo: dict[tuple[int, int], pd.DataFrame | None] = {}
        self.requests = 0
        self.failures = 0

    def _get(self, url: str) -> bytes:
        for wait in (*RETRY_WAITS_S, None):
            gap = MIN_REQUEST_GAP_S - (time.monotonic() - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.monotonic()
            self.requests += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if wait is None:
                    raise
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def station_year(self, station_id: int, year: int) -> pd.DataFrame | None:
        key = (station_id, year)
        if key in self._memo:
            return self._memo[key]
        path = DAILY_DIR / str(station_id) / f"{year}.csv"
        if not path.exists():
            params = {
                "format": "csv",
                "stationID": station_id,
                "Year": year,
                "Month": 1,
                "Day": 14,
                "timeframe": 2,
                "submit": "Download Data",
            }
            try:
                body = self._get(f"{BULK_URL}?{urllib.parse.urlencode(params)}")
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                self.failures += 1
                self._memo[key] = None  # not cached: retried on the next run
                return None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        try:
            frame = weather.parse_daily_csv(path)
        except (ValueError, pd.errors.ParserError):
            frame = None
        self._memo[key] = frame
        return frame

    def daily(self, station_id: int, years: list[int]) -> pd.DataFrame | None:
        frames = [self.station_year(station_id, y) for y in years]
        if any(f is None for f in frames):
            return None
        return pd.concat(frames).sort_index()


def ensure_inventory() -> None:
    if INVENTORY_PATH.exists():
        return
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(INVENTORY_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        INVENTORY_PATH.write_bytes(resp.read())


def load_inventory() -> pd.DataFrame:
    inv = pd.read_csv(INVENTORY_PATH, skiprows=3, encoding="utf-8-sig")
    inv = inv.rename(
        columns={
            "Station ID": "station_id",
            "Latitude (Decimal Degrees)": "lat",
            "Longitude (Decimal Degrees)": "lon",
            "DLY First Year": "dly_first",
            "DLY Last Year": "dly_last",
            "Name": "name",
        }
    )
    inv = inv.dropna(subset=["dly_first", "dly_last", "lat", "lon"])
    return inv[
        ["station_id", "name", "lat", "lon", "dly_first", "dly_last"]
    ].reset_index(drop=True)


def candidates(
    inv: pd.DataFrame, lat: float, lon: float, years: list[int]
) -> pd.DataFrame:
    ok = (inv["dly_first"] <= min(years)) & (inv["dly_last"] >= max(years))
    pool = inv[ok].copy()
    pool["km"] = haversine_km(lat, lon, pool["lat"].to_numpy(), pool["lon"].to_numpy())
    pool = pool[pool["km"] <= MAX_SEARCH_KM].sort_values("km")
    return pool.head(MAX_CANDIDATES)


def match_incident(
    dl: Downloader, inv: pd.DataFrame, lat: float, lon: float, d0: date
) -> dict[str, object]:
    years = sorted({(d0 - timedelta(days=LOOKBACK_DAYS)).year, d0.year})
    cands = candidates(inv, lat, lon, years)
    row: dict[str, object] = dict.fromkeys(weather.FEATURE_NAMES, math.nan)
    for group, (usable, features) in GROUPS.items():
        row[f"{group}_station_id"] = None
        row[f"{group}_station_km"] = math.nan
        for cand in cands.itertuples():
            daily = dl.daily(int(cand.station_id), years)
            if daily is not None and usable(daily, d0):
                row.update(features(daily, d0))
                row[f"{group}_station_id"] = int(cand.station_id)
                row[f"{group}_station_km"] = round(float(cand.km), 1)
                break
    return row


def build(limit: int | None) -> pd.DataFrame:
    ensure_inventory()
    inv = load_inventory()
    cer = load_cer()
    cer = cer[cer["event_date"].notna()].sort_values(["Latitude", "Longitude"])
    cer = cer.rename(columns={"Incident Number": "incident_number"})
    if limit:
        cer = cer.head(limit)
    dl = Downloader()
    rows = []
    for i, inc in enumerate(cer.itertuples(), 1):
        d0 = inc.event_date.date()
        row = match_incident(dl, inv, float(inc.Latitude), float(inc.Longitude), d0)
        rows.append(
            {
                "incident_number": inc.incident_number,
                "event_date": d0.isoformat(),
                **row,
            }
        )
        if i % 50 == 0:
            print(
                f"  {i}/{len(cer)} incidents · {dl.requests} requests · "
                f"{dl.failures} failed",
                flush=True,
            )
    print(f"done: {len(rows)} incidents, {dl.requests} requests, {dl.failures} failed")
    return pd.DataFrame(rows)


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def coverage_rows(out: pd.DataFrame, mask: pd.Series) -> list[str]:
    lines = []
    sub = out[mask]
    for group in GROUPS:
        km = sub[f"{group}_station_km"]
        matched = km.notna()
        near = (km <= PREFERRED_KM).mean()
        med = f"{km.median():.1f}" if matched.any() else "—"
        lines.append(f"| {group} | {pct(matched.mean())} | {pct(near)} | {med} |")
    return lines


def write_report(out: pd.DataFrame) -> None:
    cer = load_cer().set_index("Incident Number")
    ab = out["incident_number"].map(cer["is_alberta"]).fillna(False).astype(bool)
    head = "| variable group | matched | within 50 km | median km |\n|---|---|---|---|"
    feature_cov = [
        f"| `{f}` | {pct(out[f].notna().mean())} | {pct(out.loc[ab, f].notna().mean())} |"
        for f in weather.FEATURE_NAMES
    ]
    text = "\n\n".join(
        [
            "# Weather enrichment — coverage",
            (
                "Generated by `scripts/fetch_weather.py`. Source: Environment and Climate Change "
                "Canada, Historical Climate Data (daily). Nearest station with usable data in "
                f"the window, searched up to {MAX_SEARCH_KM:.0f} km (preferred ≤ "
                f"{PREFERRED_KM:.0f} km), chosen separately per variable group. Unmatched "
                "features are **missing, not zero**."
            ),
            f"## National ({len(out):,} incidents)",
            head
            + "\n"
            + "\n".join(coverage_rows(out, pd.Series(True, index=out.index))),
            f"## Alberta ({int(ab.sum()):,} incidents)",
            head + "\n" + "\n".join(coverage_rows(out, ab)),
            "## Feature fill rate",
            "| feature | national | Alberta |\n|---|---|---|\n"
            + "\n".join(feature_cov),
        ]
    )
    REPORT_PATH.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    out = build(args.limit)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")
    if args.limit is None:
        write_report(out)
        print(f"wrote {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
