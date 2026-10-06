"""Fetch the national CER Pipeline Systems layer (independent asset source).

Usage: python -m scripts.fetch_pipeline_systems
Writes:
- data/cer_pipeline_systems.csv        (attributes only, committed; ~30 rows)
- data/processed/pipelines_ca.geojson  (simplified national geometry, git-ignored)
"""

from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.fetch_pipelines import SERVICE_URL

ROOT = Path(__file__).resolve().parent.parent
ATTR_PATH = ROOT / "data" / "cer_pipeline_systems.csv"
GEOJSON_PATH = ROOT / "data" / "processed" / "pipelines_ca.geojson"
FIELDS = ("Pipeline_Name", "Company", "Commodity")
SIMPLIFY_DEG = 0.005


def query(*, geometry: bool) -> dict:
    params = {
        "where": "1=1",
        "outFields": ",".join(FIELDS),
        "returnGeometry": "true" if geometry else "false",
        "outSR": "4326",
        "f": "geojson" if geometry else "json",
    }
    if geometry:
        params |= {"maxAllowableOffset": str(SIMPLIFY_DEG), "geometryPrecision": "4"}
    url = f"{SERVICE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "FlowLine/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clean(value: object) -> str:
    return str(value or "").strip()


def write_attributes(payload: dict) -> int:
    rows = sorted(
        {tuple(clean(f["attributes"][k]) for k in FIELDS) for f in payload["features"]}
    )
    with ATTR_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pipeline_name", "company", "commodity"])
        writer.writerows(rows)
    return len(rows)


def write_geometry(payload: dict) -> int:
    for feature in payload["features"]:
        props = feature.get("properties") or {}
        feature["properties"] = {k: clean(v) for k, v in props.items()}
    GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOJSON_PATH.write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    return len(payload["features"])


def main() -> None:
    n_attr = write_attributes(query(geometry=False))
    print(f"wrote {ATTR_PATH.relative_to(ROOT)} ({n_attr} systems)")
    n_geo = write_geometry(query(geometry=True))
    size = GEOJSON_PATH.stat().st_size / 1024 / 1024
    print(f"wrote {GEOJSON_PATH.relative_to(ROOT)} ({n_geo} features, {size:.1f} MB)")


if __name__ == "__main__":
    main()
