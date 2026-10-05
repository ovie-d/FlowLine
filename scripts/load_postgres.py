"""Idempotent loader: CER incidents, weather, pipelines, ranking seed, crews, decisions.

Usage: python -m scripts.load_postgres
Needs DATABASE_URL (see .env.example) and `docker compose up -d db`.

Re-running is safe: incidents/weather are upserted; pipelines, ranking seed and
corridors are rebuilt; crew rows and decisions are only inserted when missing,
so planner edits are never overwritten.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg

from core import crew_seed
from core.cer import load_cer
from core.data import DATA_PATH, clear_load_cache, load_incidents
from core.db import INCIDENT_COLUMNS, db_path
from core.env import load_dotenv
from core.pg import connect
from core.similar import VECTOR_DIM, WEATHER_SCALES, context_vector, vector_literal
from core.sites import assign_sites
from core.storage import DECISIONS_PATH
from core.taxonomy import MODEL_TARGETS, all_hazards
from core.weather import FEATURE_NAMES as WEATHER_FEATURES

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
WEATHER_PATH = ROOT / "data" / "processed" / "incident_weather.csv"
PIPELINES_NATIONAL = ROOT / "data" / "processed" / "pipelines_ca.geojson"
PIPELINES_AB = ROOT / "public" / "pipelines_ab.geojson"

POINT_SQL = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"
WEATHER_STATION_COLS = (
    "temp_station_id",
    "temp_station_km",
    "precip_station_id",
    "precip_station_km",
    "snow_station_id",
    "snow_station_km",
)


def clean(value: Any) -> Any:
    """NaN/NaT -> None; pandas/numpy scalars -> plain Python."""
    if value is None or isinstance(value, (str, list, dict, tuple)):
        return value
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value.item() if hasattr(value, "item") else value


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def date_source(row: pd.Series) -> str:
    if pd.notna(row["occurred"]):
        return "occurred"
    return "discovered" if pd.notna(row["discovered"]) else "reported"


def incident_rows(cer: pd.DataFrame) -> list[tuple]:
    raw_cols = [c for c in cer.columns if c[0].isupper()]
    sites = assign_sites(cer["Latitude"].to_numpy(), cer["Longitude"].to_numpy())
    rows = []
    for (_, r), site in zip(cer.iterrows(), sites, strict=True):
        raw = {c.strip(): clean(r[c]) for c in raw_cols}
        groups = all_hazards(
            r["Detailed what happened"]
            if pd.notna(r["Detailed what happened"])
            else None
        )
        rows.append(
            (
                r["Incident Number"],
                r["event_date"].date(),
                date_source(r),
                clean(r["occurred"]),
                clean(r["discovered"]),
                r["reported"].date() if pd.notna(r["reported"]) else None,
                r["Province"],
                bool(r["is_alberta"]),
                clean(str(r["Nearest Populated Centre"]).strip() or None),
                r["Company"].strip(),
                r["operator_group"],
                r["commodity"],
                clean(r["Status"]),
                float(r["Latitude"]),
                float(r["Longitude"]),
                float(r["Longitude"]),
                float(r["Latitude"]),
                int(site),
                r["hazard_group"],
                groups or [r["hazard_group"]],
                r["hazard_group"] in MODEL_TARGETS,
                clean(r["Incident Types"]),
                clean(r["What happened category"]),
                clean(r["Detailed what happened"]),
                clean(r["Why it happened category"]),
                clean(r["Detailed why it happened"]),
                json.dumps(raw, default=str),
                r["closed"].date() if pd.notna(r["closed"]) else None,
            )
        )
    return rows


INCIDENT_COLS = (
    "incident_number, event_date, event_date_source, occurred_at, discovered_at, "
    "reported_date, province, is_alberta, nearest_centre, company, operator_group, "
    "commodity, status, latitude, longitude, geom, site_id, hazard_group, hazard_groups, "
    "is_model_target, incident_types, what_category, detailed_what, why_category, "
    "detailed_why, raw, closed_date"
)
INCIDENT_UPDATE = ", ".join(
    f"{c.strip()} = EXCLUDED.{c.strip()}"
    for c in INCIDENT_COLS.split(",")
    if c.strip() != "incident_number"
)


def load_incident_table(conn: psycopg.Connection) -> int:
    cer = load_cer()
    cer = cer[cer["event_date"].notna()]
    placeholders = (
        ", ".join(["%s"] * 15)
        + f", {POINT_SQL}, "
        + ", ".join(["%s"] * 9)
        + ", %s::jsonb, %s"
    )
    conn.cursor().executemany(
        f"INSERT INTO incidents ({INCIDENT_COLS}, loaded_at) "
        f"VALUES ({placeholders}, now()) "
        f"ON CONFLICT (incident_number) DO UPDATE SET {INCIDENT_UPDATE}, loaded_at = now()",
        incident_rows(cer),
    )
    return len(cer)


def load_weather(conn: psycopg.Connection) -> int:
    if not WEATHER_PATH.exists():
        return 0
    wx = pd.read_csv(WEATHER_PATH)
    known = {
        r["incident_number"]
        for r in conn.execute("SELECT incident_number FROM incidents")
    }
    wx = wx[wx["incident_number"].isin(known)]
    cols = ["incident_number", *WEATHER_FEATURES, *WEATHER_STATION_COLS]
    rows = [tuple(clean(v) for v in rec) for rec in wx[cols].itertuples(index=False)]
    rows = [
        tuple(
            int(v) if c.endswith("_station_id") and v is not None else v
            for c, v in zip(cols, r, strict=True)
        )
        for r in rows
    ]
    update = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols[1:])
    conn.cursor().executemany(
        f"INSERT INTO incident_weather ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) "
        f"ON CONFLICT (incident_number) DO UPDATE SET {update}",
        rows,
    )
    return len(rows)


def load_context(conn: psycopg.Connection) -> tuple[int, int]:
    """Structured context vectors (core.similar) + national weather medians."""
    names = list(WEATHER_SCALES)
    medians_row = conn.execute(
        "SELECT "
        + ", ".join(
            f"percentile_cont(0.5) WITHIN GROUP (ORDER BY {n}) AS {n}" for n in names
        )
        + " FROM incident_weather"
    ).fetchone()
    medians = {n: float(medians_row[n] or 0.0) for n in names}
    conn.execute(
        "INSERT INTO similarity_meta (id, medians, scales) VALUES (1, %s::jsonb, %s::jsonb) "
        "ON CONFLICT (id) DO UPDATE SET medians = EXCLUDED.medians, "
        "scales = EXCLUDED.scales, updated_at = now()",
        (json.dumps(medians), json.dumps(WEATHER_SCALES)),
    )
    rows = conn.execute(
        "SELECT i.incident_number, i.latitude, i.longitude, i.event_date, i.commodity, "
        + ", ".join(f"w.{n}" for n in names)
        + " FROM incidents i LEFT JOIN incident_weather w USING (incident_number)"
    ).fetchall()
    out = []
    for r in rows:
        vec, known = context_vector(
            r["latitude"],
            r["longitude"],
            r["event_date"],
            {n: r[n] for n in names},
            r["commodity"],
            medians,
        )
        assert len(vec) == VECTOR_DIM
        out.append((r["incident_number"], vector_literal(vec), known))
    conn.cursor().executemany(
        "INSERT INTO incident_context (incident_number, vec, weather_known) "
        "VALUES (%s, %s::vector, %s) ON CONFLICT (incident_number) DO UPDATE "
        "SET vec = EXCLUDED.vec, weather_known = EXCLUDED.weather_known",
        out,
    )
    return len(out), sum(1 for *_, k in out if k)


def load_pipelines(conn: psycopg.Connection) -> tuple[int, str]:
    path = PIPELINES_NATIONAL if PIPELINES_NATIONAL.exists() else PIPELINES_AB
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    conn.execute("TRUNCATE pipelines RESTART IDENTITY")
    rows = [
        (
            str(f["properties"].get("Pipeline_Name", "")).strip(),
            str(f["properties"].get("Company", "")).strip(),
            str(f["properties"].get("Commodity", "")).strip().lower(),
            json.dumps(f["geometry"]),
        )
        for f in features
        if f.get("geometry")
    ]
    conn.cursor().executemany(
        "INSERT INTO pipelines (pipeline_name, company, commodity, geom) "
        "VALUES (%s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))::geography)",
        rows,
    )
    return len(rows), str(path.relative_to(ROOT))


def update_pipeline_distance(conn: psycopg.Connection) -> int:
    """Distance (km) from each incident to the nearest CER pipeline system."""
    conn.execute(
        "UPDATE incidents i SET dist_pipeline_km = d.km FROM ("
        " SELECT i2.incident_number, ("
        "   SELECT ST_Distance(i2.geom, p.geom) / 1000.0 FROM pipelines p"
        "   ORDER BY i2.geom <-> p.geom LIMIT 1) AS km"
        " FROM incidents i2) d WHERE d.incident_number = i.incident_number"
    )
    return conn.execute(
        "SELECT count(*) AS n FROM incidents WHERE dist_pipeline_km IS NOT NULL"
    ).fetchone()["n"]


def load_ranking(conn: psycopg.Connection) -> tuple[int, int]:
    """Ranking seed (313 rows) + cleaned corridors for the existing ranking tab."""
    seed = pd.read_csv(DATA_PATH)
    conn.execute("TRUNCATE ranking_incidents RESTART IDENTITY")
    rows = [
        tuple(
            str(pd.Timestamp(v).date()) if c == "date" and pd.notna(v) else clean(v)
            for c, v in zip(INCIDENT_COLUMNS, rec, strict=True)
        )
        for rec in seed[list(INCIDENT_COLUMNS)].itertuples(index=False)
    ]
    conn.cursor().executemany(
        f"INSERT INTO ranking_incidents ({', '.join(INCIDENT_COLUMNS)}) "
        f"VALUES ({', '.join(['%s'] * len(INCIDENT_COLUMNS))})",
        rows,
    )
    conn.commit()
    clear_load_cache()
    cleaned, _ = load_incidents()
    corridors = cleaned.groupby("corridor").agg(
        n=("corridor", "size"), lat=("latitude", "mean"), lon=("longitude", "mean")
    )
    conn.execute("TRUNCATE corridors")
    conn.cursor().executemany(
        f"INSERT INTO corridors (name, n_incidents, latitude, longitude, geom) "
        f"VALUES (%s, %s, %s, %s, {POINT_SQL})",
        [
            (name, int(r.n), float(r.lat), float(r.lon), float(r.lon), float(r.lat))
            for name, r in corridors.iterrows()
        ],
    )
    return len(rows), len(corridors)


def seed_crews(conn: psycopg.Connection) -> tuple[int, int, int]:
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO crew_types (id, name, description, is_sample) VALUES (%s, %s, %s, true) "
        "ON CONFLICT (id) DO NOTHING",
        [(k, name, desc) for k, (name, desc) in crew_seed.CREW_TYPES.items()],
    )
    cur.executemany(
        "INSERT INTO hazard_crew_map (hazard_group, crew_type_id, equipment, priority, "
        "is_sample) VALUES (%s, %s, %s, %s, true) "
        "ON CONFLICT (hazard_group, crew_type_id) DO NOTHING",
        [
            (hazard, crew, equipment, priority)
            for hazard, crews in crew_seed.HAZARD_CREW_MAP.items()
            for crew, equipment, priority in crews
        ],
    )
    cur.executemany(
        "INSERT INTO crew_bases (id, name, province, latitude, longitude, geom, crew_types, "
        f"is_sample) VALUES (%s, %s, %s, %s, %s, {POINT_SQL}, %s, true) "
        "ON CONFLICT (id) DO NOTHING",
        [
            (k, name, prov, lat, lon, lon, lat, crews)
            for k, (name, prov, lat, lon, crews) in crew_seed.CREW_BASES.items()
        ],
    )
    counts = conn.execute(
        "SELECT (SELECT count(*) FROM crew_types) AS t, "
        "(SELECT count(*) FROM hazard_crew_map) AS m, (SELECT count(*) FROM crew_bases) AS b"
    ).fetchone()
    return counts["t"], counts["m"], counts["b"]


def existing_decisions() -> list[dict[str, Any]]:
    """Decisions from the JSON log and the legacy SQLite DB, if present."""
    found: list[dict[str, Any]] = []
    if DECISIONS_PATH.exists():
        data = json.loads(DECISIONS_PATH.read_text() or "[]")
        found += [d for d in data if isinstance(d, dict)]
    sqlite_path = db_path()
    if sqlite_path.exists():
        with sqlite3.connect(str(sqlite_path)) as lite:
            lite.row_factory = sqlite3.Row
            try:
                rows = lite.execute("SELECT * FROM decisions").fetchall()
            except sqlite3.Error:
                rows = []
        found += [
            {**dict(r), "policy": json.loads(r["policy_json"] or "{}")} for r in rows
        ]
    return found


def migrate_decisions(conn: psycopg.Connection) -> tuple[int, int]:
    found = existing_decisions()
    conn.cursor().executemany(
        "INSERT INTO decision_log (id, ts, corridor, action, priority, reason, policy, source) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) ON CONFLICT (id) DO NOTHING",
        [
            (
                d["id"],
                d["ts"],
                d["corridor"],
                d["action"],
                str(d.get("priority", "")),
                d["reason"],
                json.dumps(d.get("policy") or {}),
                d.get("source", "planner"),
            )
            for d in found
        ],
    )
    total = conn.execute("SELECT count(*) AS n FROM decision_log").fetchone()["n"]
    return len(found), total


def main() -> None:
    load_dotenv()
    with connect() as conn:
        apply_schema(conn)
        n_inc = load_incident_table(conn)
        print(f"incidents: {n_inc} upserted")
        print(f"incident_weather: {load_weather(conn)} upserted")
        n_ctx, n_known = load_context(conn)
        print(f"incident_context: {n_ctx} vectors ({n_known} with full weather)")
        n_pipe, src = load_pipelines(conn)
        print(f"pipelines: {n_pipe} from {src}")
        print(f"dist_pipeline_km: {update_pipeline_distance(conn)} incidents")
        conn.commit()
        n_seed, n_corr = load_ranking(conn)
        print(f"ranking_incidents: {n_seed} · corridors: {n_corr}")
        t, m, b = seed_crews(conn)
        print(f"crew_types: {t} · hazard_crew_map: {m} · crew_bases: {b} (sample data)")
        found, total = migrate_decisions(conn)
        print(f"decision_log: {found} found in JSON/SQLite · {total} in Postgres")
        conn.commit()


if __name__ == "__main__":
    main()
