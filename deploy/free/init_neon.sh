#!/usr/bin/env bash
# Load the public Flowline database snapshot into a Neon (or any PostGIS + pgvector)
# database. The connection string is read from a file you create, so it never appears
# in a command line or chat:
#   deploy/free/init_neon.sh ~/.flowline-neon-url
# Builds the snapshot first if needed (deploy/huggingface/publish.py <user> bundle).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
URL_FILE="${1:?usage: init_neon.sh <file containing the connection string>}"
URL="$(tr -d '[:space:]' < "$URL_FILE")"
DUMP="$ROOT/deploy/huggingface/.bundle/flowline-db.dump"
[[ -f "$DUMP" ]] || (cd "$ROOT" && .venv/bin/python deploy/huggingface/publish.py local bundle)

# PostgreSQL 18 client tools from the project's database image (no local install needed).
pg() {
  local cmd="docker run --rm -i --network host -e PGURL -v $ROOT/deploy/huggingface/.bundle:/b:ro flowline-db:18-3.6-pgvector $*"
  if docker info >/dev/null 2>&1; then PGURL="$URL" bash -c "$cmd"; else PGURL="$URL" sg docker -c "$cmd"; fi
}
echo "Creating extensions…"
pg 'sh -c "psql \"\$PGURL\" -q -c \"CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;\""'
echo "Restoring the public snapshot (incidents, weather, similarity, pipelines, crossings)…"
pg 'sh -c "pg_restore --no-owner --no-privileges --clean --if-exists -d \"\$PGURL\" /b/flowline-db.dump"' || true
echo "Applying the schema and seeding the sample crew table…"
cd "$ROOT"
FLOWLINE_INIT_URL="$URL" .venv/bin/python - <<'PY'
import os

import psycopg

from scripts import load_postgres

with psycopg.connect(os.environ["FLOWLINE_INIT_URL"], row_factory=psycopg.rows.dict_row) as conn:
    load_postgres.apply_schema(conn)
    print("crews seeded (types, map, bases):", load_postgres.seed_crews(conn))
    n = conn.execute("SELECT count(*) AS n FROM incidents").fetchone()["n"]
    c = conn.execute("SELECT count(*) AS n FROM waterway_crossings").fetchone()["n"]
    print(f"incidents: {n} · river crossings: {c}")
PY
echo "Done."
