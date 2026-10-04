#!/usr/bin/env python3
"""Fetch CER pipeline routes (Alberta bbox) once → public/pipelines_ab.geojson.

The app loads the static file; it never calls ArcGIS at runtime.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Next.js serves static assets from public/ (there is no frontend/ folder here).
OUT_PATH = ROOT / "public" / "pipelines_ab.geojson"

SERVICE_URL = (
    "https://services5.arcgis.com/vNzamREXvX2WcX6d/ArcGIS/rest/services/"
    "CER_Pipeline_Systems_WGS84_WM_v/FeatureServer/0/query"
)

PAGE_SIZE = 2000
MAX_BYTES = 2 * 1024 * 1024  # 2 MB


def fetch_page(
    *,
    result_offset: int,
    max_allowable_offset: float,
) -> dict:
    params = {
        "where": "1=1",
        "geometry": "-120,49,-110,60",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Pipeline_Name,Company,Commodity",
        "returnGeometry": "true",
        "outSR": "4326",
        "maxAllowableOffset": str(max_allowable_offset),
        "geometryPrecision": "4",
        "f": "geojson",
        "resultOffset": str(result_offset),
        "resultRecordCount": str(PAGE_SIZE),
    }
    url = f"{SERVICE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "FlowLine/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(max_allowable_offset: float) -> dict:
    features: list[dict] = []
    offset = 0
    while True:
        print(f"  fetching offset={offset} (offset_tol={max_allowable_offset})…")
        page = fetch_page(
            result_offset=offset,
            max_allowable_offset=max_allowable_offset,
        )
        batch = page.get("features") or []
        features.extend(batch)
        exceeded = page.get("exceededTransferLimit", False)
        print(f"    got {len(batch)} features (total {len(features)})")
        if len(batch) < PAGE_SIZE or exceeded is False:
            break
        offset += PAGE_SIZE

    return {"type": "FeatureCollection", "features": features}


def write_collection(collection: dict) -> tuple[int, int]:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(collection, separators=(",", ":"))
    OUT_PATH.write_text(payload, encoding="utf-8")
    count = len(collection["features"])
    size = OUT_PATH.stat().st_size
    return count, size


def main() -> int:
    offset_tol = 0.005
    print(f"Querying CER pipelines → {OUT_PATH.relative_to(ROOT)}")
    collection = fetch_all(offset_tol)
    count, size = write_collection(collection)
    print(f"Wrote {count} features, {size:,} bytes ({size / 1024 / 1024:.2f} MB)")

    if size > MAX_BYTES:
        print(
            f"File exceeds 2 MB — re-running with maxAllowableOffset=0.01…"
        )
        offset_tol = 0.01
        collection = fetch_all(offset_tol)
        count, size = write_collection(collection)
        print(
            f"Wrote {count} features, {size:,} bytes ({size / 1024 / 1024:.2f} MB)"
        )

    if size > MAX_BYTES:
        print(
            f"WARNING: still {size / 1024 / 1024:.2f} MB after simplification.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
