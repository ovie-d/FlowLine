"""Load + clean CER Alberta incidents; derive per-incident features."""

from __future__ import annotations

import math
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import RiskConfig
from core.db import INCIDENT_COLUMNS, db_path
from core.pg import try_connect

DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "cer_pipeline_incidents_alberta_2015.csv"
)

# Alphabetized alias map: raw spelling -> canonical corridor name.
CORRIDOR_ALIASES: dict[str, str] = {
    "Edmoton": "Edmonton",
    "Edson AB": "Edson",
    "Edson Ab": "Edson",
    "Edson Alberta": "Edson",
    "FT MacKy": "Fort McKay",
    "Fort Mcmurray": "Fort McMurray",
    "Grande Cache AB": "Grande Cache",
    "Hardisty AB": "Hardisty",
    "Hardisty Alberta": "Hardisty",
    "Manning AB": "Manning",
    "Sherwood Park AB": "Sherwood Park",
    "Town of Japser": "Jasper",
    "Zama": "Zama City",
}

# Alphabetized junk corridor names snapped by lat/lon.
JUNK_CORRIDORS: frozenset[str] = frozenset(
    {
        "17",
        "8500",
        "Karr Receipt Point is approximately 95 km SE of Grande Prairie",
    }
)

SNAP_RADIUS_KM = 40.0

CRUDE_OR_LIQUID: frozenset[str] = frozenset(
    {
        "Condensate",
        "Diesel Fuel",
        "Lube Oil",
        "crude Sweet",
        "crude Synthetic",
    }
)

GAS_SUBSTANCES: frozenset[str] = frozenset(
    {
        "Natural Gas Liquids",
        "Sweet",
    }
)

HARM_TYPES: frozenset[str] = frozenset(
    {
        "Explosion",
        "Fatality",
        "Serious Injury (as defined in the OPR)",
    }
)

FACILITY_TYPES: frozenset[str] = frozenset(
    {
        "Fire",
        "Operation Beyond Design Limits",
    }
)

UPSTREAM_DROPPED_NO_DATE = 141


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _substance_class(substance: str) -> str:
    if substance in CRUDE_OR_LIQUID:
        return "liquid"
    if substance in GAS_SUBSTANCES:
        return "gas"
    if isinstance(substance, str) and "sour" in substance.lower():
        return "gas"
    if substance == "Not Applicable" or not substance:
        return "none"
    return "none"


def _event_class(incident_type: str) -> str:
    if incident_type in FACILITY_TYPES:
        return "facility_event"
    if incident_type in {"Explosion", "Fatality"} or incident_type.startswith(
        "Serious Injury"
    ):
        return "harm"
    if incident_type in {"Release of Substance", "Adverse Environmental Effects"}:
        return "release"
    return "release"


def _is_sour(substance: str) -> bool:
    return isinstance(substance, str) and "sour" in substance.lower()


def _is_crude(substance: str) -> bool:
    return isinstance(substance, str) and substance.lower().startswith("crude")


def severity_v2_for_row(row: pd.Series, config: RiskConfig) -> str:
    """Label one incident under severity_v2 rules."""
    incident_type = str(row.get("incident_type", ""))
    substance = str(row.get("substance", "")) if pd.notna(row.get("substance")) else ""
    release = row.get("release_m3")

    if incident_type in {"Explosion", "Fatality"}:
        return "high"
    if _is_crude(substance) or _is_sour(substance):
        return "high"
    if (
        substance in CRUDE_OR_LIQUID
        and pd.notna(release)
        and float(release) >= config.liquid_high_m3
    ):
        return "high"
    if (
        _substance_class(substance) == "gas"
        and pd.notna(release)
        and float(release) >= config.gas_high_m3
    ):
        return "high"
    if incident_type.startswith("Serious Injury"):
        return "medium"
    if incident_type == "Adverse Environmental Effects":
        return "medium"
    if incident_type == "Release of Substance":
        return "medium"
    if incident_type in FACILITY_TYPES:
        return "low"
    return "medium"


def _apply_aliases(series: pd.Series) -> tuple[pd.Series, dict[str, int]]:
    mapped = series.map(lambda c: CORRIDOR_ALIASES.get(c, c))
    merge_counts: dict[str, int] = {}
    for raw, canon in CORRIDOR_ALIASES.items():
        n = int((series == raw).sum())
        if n:
            merge_counts[f"{raw} -> {canon}"] = n
    return mapped, merge_counts


def _snap_junk(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    out = df.copy()
    snaps: list[dict[str, Any]] = []
    junk_mask = out["corridor"].isin(JUNK_CORRIDORS)
    if not junk_mask.any():
        return out, snaps

    good = out[~junk_mask]
    centroids = good.groupby("corridor", sort=True)[["latitude", "longitude"]].mean()

    for idx in out.index[junk_mask]:
        row = out.loc[idx]
        lat, lon = float(row["latitude"]), float(row["longitude"])
        best_name: str | None = None
        best_km = float("inf")
        for name, cent in centroids.iterrows():
            d = _haversine_km(
                lat, lon, float(cent["latitude"]), float(cent["longitude"])
            )
            if d < best_km:
                best_km = d
                best_name = str(name)
        if best_name is not None and best_km <= SNAP_RADIUS_KM:
            new_name = best_name
        else:
            new_name = f"Unnamed ({lat:.2f},{lon:.2f})"
        snaps.append(
            {
                "corridor_raw": row["corridor_raw"],
                "snapped_to": new_name,
                "distance_km": round(best_km, 2),
            }
        )
        out.at[idx, "corridor"] = new_name
    return out, snaps


def _derive_features(df: pd.DataFrame, config: RiskConfig) -> pd.DataFrame:
    out = df.copy()
    latest = out["date"].max()
    out["substance_class"] = out["substance"].map(
        lambda s: _substance_class(s if pd.notna(s) else "")
    )
    out["event_class"] = out["incident_type"].map(_event_class)
    out["severity_lab"] = out["consequence"]
    out["severity_v2"] = out.apply(lambda r: severity_v2_for_row(r, config), axis=1)
    out["age_years"] = (latest - out["date"]).dt.days / 365.25
    return out


def _read_raw_from_db(path: Path) -> pd.DataFrame | None:
    """Return raw seed columns from SQLite, or None if unavailable/empty."""
    if not path.exists():
        return None
    try:
        with sqlite3.connect(str(path)) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='incidents'"
            ).fetchone()
            if not tables:
                return None
            count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            if not count:
                return None
            cols = ", ".join(INCIDENT_COLUMNS)
            raw = pd.read_sql_query(
                f"SELECT {cols} FROM incidents ORDER BY id",
                conn,
                parse_dates=["date"],
            )
    except (sqlite3.Error, ValueError, OSError):
        return None
    return raw


def _pg_ranking_stamp() -> str | None:
    """'count:max(loaded_at)' of Postgres ranking_incidents, or None if unusable."""
    conn = try_connect()
    if conn is None:
        return None
    try:
        with conn:
            row = conn.execute(
                "SELECT count(*) AS n, max(loaded_at) AS ts FROM ranking_incidents"
            ).fetchone()
    except Exception:  # noqa: BLE001 — missing table / server error -> other sources
        return None
    if not row or not row["n"]:
        return None
    return f"{row['n']}:{row['ts']}"


def _read_raw_from_pg() -> pd.DataFrame | None:
    conn = try_connect()
    if conn is None:
        return None
    cols = ", ".join(INCIDENT_COLUMNS)
    try:
        with conn:
            rows = conn.execute(
                f"SELECT {cols} FROM ranking_incidents ORDER BY id"
            ).fetchall()
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    raw = pd.DataFrame(rows, columns=list(INCIDENT_COLUMNS))
    raw["date"] = pd.to_datetime(raw["date"])
    return raw


def _read_raw_incidents() -> tuple[pd.DataFrame, str]:
    """Prefer Postgres (DATABASE_URL), then SQLite (DB_PATH), else CSV."""
    if _pg_ranking_stamp() is not None:
        raw = _read_raw_from_pg()
        if raw is not None:
            return raw, "postgres:ranking_incidents"
    db = db_path()
    raw = _read_raw_from_db(db)
    if raw is not None:
        return raw, f"db:{db.resolve()}"
    return pd.read_csv(DATA_PATH, parse_dates=["date"]), f"csv:{DATA_PATH.resolve()}"


def _incident_source_key() -> str:
    """Cache key so switching DB_PATH / reloading seed invalidates cleanly."""
    stamp = _pg_ranking_stamp()
    if stamp is not None:
        return f"postgres:{stamp}"
    db = db_path()
    raw = _read_raw_from_db(db)
    if raw is not None:
        mtime = db.stat().st_mtime_ns
        return f"db:{db.resolve()}:{mtime}:{len(raw)}"
    mtime = DATA_PATH.stat().st_mtime_ns if DATA_PATH.exists() else 0
    return f"csv:{DATA_PATH.resolve()}:{mtime}"


@lru_cache(maxsize=8)
def _load_cached(source_key: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load and clean once. Callers must .copy() before mutating."""
    _ = source_key
    raw, source = _read_raw_incidents()
    corridors_before = int(raw["corridor"].nunique())
    n_loaded = len(raw)

    missing_date = int(raw["date"].isna().sum())
    df = raw.dropna(subset=["date"]).reset_index(drop=True)

    df["corridor_raw"] = df["corridor"]
    df["corridor"], merge_counts = _apply_aliases(df["corridor"])
    df, snaps = _snap_junk(df)

    # Default thresholds for severity_v2 at load time; scoring can recompute
    # if gas/liquid thresholds change via config.
    default_cfg = RiskConfig()
    df = _derive_features(df, default_cfg)

    relabel = {
        "lab": df["severity_lab"].value_counts().to_dict(),
        "v2": df["severity_v2"].value_counts().to_dict(),
    }
    # JSON-safe int keys/values
    relabel = {
        k: {str(sk): int(sv) for sk, sv in v.items()} for k, v in relabel.items()
    }

    report: dict[str, Any] = {
        "rows_loaded": n_loaded,
        "rows_dropped_no_date": missing_date,
        "rows_scored": len(df),
        "upstream_dropped_no_date": UPSTREAM_DROPPED_NO_DATE,
        "corridors_before": corridors_before,
        "corridors_after": int(df["corridor"].nunique()),
        "alias_merges": merge_counts,
        "snaps": snaps,
        "relabel_counts": relabel,
        "source": source,
    }
    return df, report


def load_incidents(
    config: RiskConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return a cleaned DataFrame copy and cleaning report.

    If ``config`` changes volume thresholds vs defaults, severity_v2 is recomputed.
    """
    df, report = _load_cached(_incident_source_key())
    out = df.copy()
    report = dict(report)

    cfg = config or RiskConfig()
    default = RiskConfig()
    if (
        cfg.gas_high_m3 != default.gas_high_m3
        or cfg.liquid_high_m3 != default.liquid_high_m3
    ):
        out["severity_v2"] = out.apply(lambda r: severity_v2_for_row(r, cfg), axis=1)
        report["relabel_counts"] = {
            "lab": {
                str(k): int(v) for k, v in out["severity_lab"].value_counts().items()
            },
            "v2": {
                str(k): int(v) for k, v in out["severity_v2"].value_counts().items()
            },
        }

    if not cfg.include_facility_events:
        out = out[out["event_class"] != "facility_event"].reset_index(drop=True)
        report["rows_scored"] = len(out)
        report["corridors_after"] = int(out["corridor"].nunique())
        report["excluded_facility_events"] = True

    return out, report


def clear_load_cache() -> None:
    """Test helper."""
    _load_cached.cache_clear()
