#!/usr/bin/env bash
# Runtime: start the database, router, API and web app; stop the container if any exits
# (Hugging Face then restarts it).
set -uo pipefail
cd "$HOME/app"
pg_ctl -D "$HOME/pgdata" -o "-c listen_addresses=127.0.0.1 -p 5432 -k /tmp" -w start
osrm-routed --algorithm mld --max-table-size 1000 --ip 127.0.0.1 --port 5000 \
  osrm/alberta-latest.osrm &
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1 &
node_modules/.bin/next start -H 0.0.0.0 -p 7860 &
wait -n
echo "A Flowline service stopped; exiting so the Space restarts." >&2
exit 1
