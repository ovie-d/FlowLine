#!/usr/bin/env python3
"""Create SQLite DB and load the CER seed CSV into ``incidents`` (idempotent)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.data import DATA_PATH
from core.db import INCIDENT_COLUMNS, connect, db_path, init_schema


def load_seed(csv_path: Path | None = None, database: Path | None = None) -> int:
    """Clear prior ``cer_seed`` rows, insert CSV rows, return count loaded."""
    source_csv = csv_path or DATA_PATH
    path = database or db_path()
    raw = pd.read_csv(source_csv)
    missing = [c for c in INCIDENT_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    loaded_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for record in raw[list(INCIDENT_COLUMNS)].itertuples(index=False, name=None):
        values = []
        for col, value in zip(INCIDENT_COLUMNS, record, strict=True):
            if pd.isna(value):
                values.append(None)
            elif col == "date":
                # Store ISO date string (YYYY-MM-DD).
                values.append(str(pd.Timestamp(value).date()))
            else:
                values.append(value)
        rows.append((*values, "cer_seed", loaded_at))

    placeholders = ", ".join("?" for _ in range(len(INCIDENT_COLUMNS) + 2))
    columns_sql = ", ".join((*INCIDENT_COLUMNS, "source", "loaded_at"))
    insert_sql = f"INSERT INTO incidents ({columns_sql}) VALUES ({placeholders})"

    with connect(path) as conn:
        init_schema(conn)
        conn.execute("DELETE FROM incidents WHERE source = 'cer_seed'")
        conn.executemany(insert_sql, rows)
        conn.commit()
        count = int(
            conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE source = 'cer_seed'"
            ).fetchone()[0]
        )
    return count


def main() -> None:
    path = db_path()
    n = load_seed(database=path)
    print(f"Loaded {n} seed incidents into {path}")


if __name__ == "__main__":
    main()
