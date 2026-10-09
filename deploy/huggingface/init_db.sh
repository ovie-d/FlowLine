#!/usr/bin/env bash
# Build time: create the database in the image from the public snapshot.
#   init_db.sh <flowline-db.dump>
set -euo pipefail
DUMP="$1"
PGDATA="$HOME/pgdata"
initdb -D "$PGDATA" -U flowline --auth=trust --encoding=UTF8 >/dev/null
pg_ctl -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -p 5432 -k /tmp" -w start >/dev/null
createdb -h 127.0.0.1 -U flowline flowline
psql -q -h 127.0.0.1 -U flowline -d flowline -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;"
pg_restore -h 127.0.0.1 -U flowline -d flowline --no-owner --no-privileges "$DUMP"
# Remaining tables (decision log, sandbox, quota) and the sample crew table.
DATABASE_URL=postgresql://flowline@127.0.0.1:5432/flowline .venv/bin/python - <<'PY'
import psycopg
from scripts import load_postgres

with psycopg.connect("postgresql://flowline@127.0.0.1:5432/flowline", row_factory=psycopg.rows.dict_row) as conn:
    load_postgres.apply_schema(conn)
    print("crews seeded:", load_postgres.seed_crews(conn))
    n = conn.execute("SELECT count(*) AS n FROM incidents").fetchone()["n"]
    print(f"incidents in snapshot: {n}")
PY
pg_ctl -D "$PGDATA" -m fast -w stop >/dev/null
