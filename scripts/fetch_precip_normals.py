"""Washout watch: download the station-years needed for prior-year rainfall normals.

Usage: python -m scripts.fetch_precip_normals
For each incident's precipitation station, fetches the NORMAL_YEARS years *before*
the incident (same cache, throttle and resume as scripts/fetch_weather.py).
"""

from __future__ import annotations

import pandas as pd

from scripts.fetch_weather import Downloader, load_inventory

WEATHER_CSV = "data/processed/incident_weather.csv"
NORMAL_YEARS = 10
LOOKBACK_DAYS = 30


def needed_station_years() -> list[tuple[int, int]]:
    wx = pd.read_csv(WEATHER_CSV, parse_dates=["event_date"]).dropna(
        subset=["precip_station_id"]
    )
    inv = load_inventory().set_index("station_id")
    need: set[tuple[int, int]] = set()
    for r in wx.itertuples():
        st = int(r.precip_station_id)
        if st not in inv.index:
            continue
        first, last = int(inv.at[st, "dly_first"]), int(inv.at[st, "dly_last"])
        start_year = (r.event_date - pd.Timedelta(days=LOOKBACK_DAYS)).year
        end_year = (r.event_date - pd.Timedelta(days=1)).year
        for k in range(1, NORMAL_YEARS + 1):
            for y in {start_year - k, end_year - k}:
                if first <= y <= last:
                    need.add((st, y))
    return sorted(need)


def main() -> None:
    need = needed_station_years()
    dl = Downloader()
    for i, (st, y) in enumerate(need, 1):
        dl.station_year(st, y)
        if i % 200 == 0:
            print(
                f"  {i}/{len(need)} station-years · {dl.requests} requests · "
                f"{dl.failures} failed",
                flush=True,
            )
    print(
        f"done: {len(need)} station-years, {dl.requests} requests, {dl.failures} failed"
    )


if __name__ == "__main__":
    main()
