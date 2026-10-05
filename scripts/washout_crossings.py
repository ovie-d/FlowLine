"""Washout watch: pipeline–waterway crossings from the Alberta OSM extract.

Usage:
  python -m scripts.washout_crossings               layer + experiment features
  python -m scripts.washout_crossings --layer-only  layer only (start.sh runs this once)
1. Loads OSM ways tagged waterway=river|stream|canal into PostGIS (table waterways).
2. Intersects them with the CER pipeline systems (table pipelines) -> crossing points
   (table waterway_crossings: the map's river-crossings layer, display only).
3. Experiment only: writes per-incident features to data/processed/incident_crossings.csv:
   dist_crossing_km (nearest crossing) and n_crossings_10km.
Only Alberta waterways are available, so incidents outside the extract's bounding
box get missing values (never zero). Crossings are static geography, known before
any incident.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import osmium
import pandas as pd

from core.env import load_dotenv
from core.pg import connect

ROOT = Path(__file__).resolve().parent.parent
PBF = ROOT / "data" / "osm" / "alberta-latest.osm.pbf"
OUT = ROOT / "data" / "processed" / "incident_crossings.csv"
WATERWAY_TYPES = frozenset({"river", "stream", "canal"})
BATCH = 5000
COUNT_RADIUS_KM = 10.0
# Alberta extract bounds (lon/lat), slightly inset so edge incidents are not mis-scored.
AB_BOUNDS = (-119.9, 49.05, -110.05, 59.95)

SCHEMA = """
DROP TABLE IF EXISTS waterways;
CREATE TABLE waterways (id bigint PRIMARY KEY, kind text NOT NULL,
                        geom geometry(LineString, 4326) NOT NULL);
"""


class WaterwayHandler(osmium.SimpleHandler):
    def __init__(self, conn) -> None:
        super().__init__()
        self.conn = conn
        self.rows: list[tuple[int, str, str]] = []
        self.count = 0

    def way(self, w) -> None:
        kind = w.tags.get("waterway")
        if kind not in WATERWAY_TYPES or len(w.nodes) < 2:
            return
        try:
            coords = ",".join(f"{n.lon:.6f} {n.lat:.6f}" for n in w.nodes)
        except osmium.InvalidLocationError:
            return
        self.rows.append((w.id, kind, f"SRID=4326;LINESTRING({coords})"))
        if len(self.rows) >= BATCH:
            self.flush()

    def flush(self) -> None:
        if self.rows:
            self.conn.cursor().executemany(
                "INSERT INTO waterways VALUES (%s, %s, ST_GeomFromEWKT(%s)) ON CONFLICT DO NOTHING",
                self.rows,
            )
            self.count += len(self.rows)
            self.rows = []


CROSSINGS_SQL = """
DROP TABLE IF EXISTS waterway_crossings;
CREATE TABLE waterway_crossings AS
SELECT row_number() OVER () AS id, w.kind, p.pipeline_name,
       (ST_Dump(ST_Intersection(p.geom::geometry, w.geom))).geom AS geom
FROM pipelines p JOIN waterways w ON ST_Intersects(p.geom::geometry, w.geom);
DELETE FROM waterway_crossings WHERE GeometryType(geom) <> 'POINT';
ALTER TABLE waterway_crossings ADD COLUMN geog geography(Point, 4326);
UPDATE waterway_crossings SET geog = geom::geography;
CREATE INDEX ON waterway_crossings USING gist (geog);
"""

FEATURES_SQL = """
SELECT i.incident_number,
       CASE WHEN i.longitude BETWEEN %(x0)s AND %(x1)s AND i.latitude BETWEEN %(y0)s AND %(y1)s
            THEN (SELECT ST_Distance(i.geom, c.geog) / 1000.0 FROM waterway_crossings c
                  ORDER BY i.geom <-> c.geog LIMIT 1) END AS dist_crossing_km,
       CASE WHEN i.longitude BETWEEN %(x0)s AND %(x1)s AND i.latitude BETWEEN %(y0)s AND %(y1)s
            THEN (SELECT count(*) FROM waterway_crossings c
                  WHERE ST_DWithin(i.geom, c.geog, %(r)s)) END AS n_crossings_10km
FROM incidents i
"""


def build_layer(conn, pbf: Path = PBF) -> int:
    """Load OSM waterways and rebuild the waterway_crossings table; returns its size."""
    conn.execute(SCHEMA)
    handler = WaterwayHandler(conn)
    handler.apply_file(str(pbf), locations=True, idx="flex_mem")
    handler.flush()
    conn.execute("CREATE INDEX ON waterways USING gist (geom)")
    conn.commit()
    print(f"waterways: {handler.count:,}")
    conn.execute(CROSSINGS_SQL)
    conn.commit()
    n = conn.execute("SELECT count(*) AS n FROM waterway_crossings").fetchone()["n"]
    print(f"pipeline–waterway crossings: {n:,}")
    return n


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline–waterway crossings from OSM."
    )
    parser.add_argument(
        "--layer-only", action="store_true", help="build the map layer only"
    )
    args = parser.parse_args()
    load_dotenv()
    if not PBF.exists():
        raise SystemExit(
            f"Missing {PBF.relative_to(ROOT)} (download the Alberta OSM extract)."
        )
    with connect() as conn:
        build_layer(conn)
        if args.layer_only:
            return
        x0, y0, x1, y1 = AB_BOUNDS
        rows = conn.execute(
            FEATURES_SQL,
            {"x0": x0, "x1": x1, "y0": y0, "y1": y1, "r": COUNT_RADIUS_KM * 1000},
        ).fetchall()
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(
        f"wrote {OUT.relative_to(ROOT)}: {df['dist_crossing_km'].notna().sum()} incidents in coverage"
    )


if __name__ == "__main__":
    main()
