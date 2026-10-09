#!/usr/bin/env bash
# Build time: create the database in the image from the public snapshot.
#   init_db.sh <flowline-db.dump>
# Uses a Unix socket only (no TCP), so it can't clash with anything on the build host.
set -euo pipefail
DUMP="$1"
PGDATA="$HOME/pgdata"
SOCK=/tmp
URL="postgresql://flowline@/flowline?host=$SOCK"
initdb -D "$PGDATA" -U flowline --auth=trust --encoding=UTF8 >/dev/null
pg_ctl -D "$PGDATA" -l "$HOME/pg_init.log" -o "-c listen_addresses='' -k $SOCK" -w start \
  || { cat "$HOME/pg_init.log"; exit 1; }
createdb -h "$SOCK" -U flowline flowline
psql -q -h "$SOCK" -U flowline -d flowline \
  -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;"
pg_restore -h "$SOCK" -U flowline -d flowline --no-owner --no-privileges "$DUMP"
# Remaining tables (decision log, sandbox, quota) and the sample crew table.
FLOWLINE_INIT_URL="$URL" .venv/bin/python - <<'PY'
import os

import psycopg

from scripts import load_postgres

with psycopg.connect(os.environ["FLOWLINE_INIT_URL"], row_factory=psycopg.rows.dict_row) as conn:
    load_postgres.apply_schema(conn)
    print("crews seeded (types, map, bases):", load_postgres.seed_crews(conn))
    n = conn.execute("SELECT count(*) AS n FROM incidents").fetchone()["n"]
    print(f"incidents in snapshot: {n}")
PY
pg_ctl -D "$PGDATA" -m fast -w stop >/dev/null
rm -f "$HOME/pg_init.log"
