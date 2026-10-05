#!/usr/bin/env bash
# Flowline one-command launcher (macOS / Linux).
#   ./start.sh            start everything and open http://localhost:3000
#   ./start.sh --no-open  same, without opening a browser
# Stop with ./stop.sh. Logs go to logs/, process ids to .run/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
OPEN_BROWSER=1
[[ "${1:-}" == "--no-open" ]] && OPEN_BROWSER=0

say()  { printf '\033[1;33m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;31m!\033[0m %s\n' "$*"; }
die()  { warn "$*"; exit 1; }

mkdir -p logs .run

# ---------------------------------------------------------------- Docker
DOCKER_MODE=""
if docker info >/dev/null 2>&1; then
  DOCKER_MODE="direct"
elif id -nG "$USER" 2>/dev/null | grep -qw docker && sg docker -c "docker info" >/dev/null 2>&1; then
  DOCKER_MODE="sg"   # user is in the docker group but this shell predates it
fi
dc() {
  if [[ "$DOCKER_MODE" == "sg" ]]; then sg docker -c "docker compose $*"; else docker compose "$@"; fi
}
if [[ -z "$DOCKER_MODE" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    say "Starting Docker Desktop…"
    open -a Docker || die "Docker Desktop is not installed."
    for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && DOCKER_MODE="direct" && break; sleep 2; done
  fi
  [[ -n "$DOCKER_MODE" ]] || die "Docker is not running or not accessible. Linux: 'sudo systemctl start docker' and make sure you are in the docker group (log out and back in)."
fi
ok "Docker is running"

# ---------------------------------------------------------------- config
if [[ ! -f .env ]]; then
  say "Creating .env from .env.example (backend settings; add GEMINI_API_KEY for the AI briefing)"
  sed -n '1,/^# Frontend/p' .env.example | grep -v '^# Frontend' > .env
fi
if [[ ! -f .env.local ]]; then
  say "Creating .env.local (frontend; add NEXT_PUBLIC_MAPBOX_TOKEN for the basemap)"
  printf 'NEXT_PUBLIC_API_URL=http://127.0.0.1:%s\nNEXT_PUBLIC_MAPBOX_TOKEN=\nNEXT_PUBLIC_MAP_STYLE=dark\n' "$API_PORT" > .env.local
fi

# ---------------------------------------------------------------- dependencies
PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  command -v python3 >/dev/null || die "python3 (3.11+) is required."
  say "Creating Python venv and installing requirements (first run only)…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# Re-install when requirements.txt changes (e.g. a new package after git pull).
REQ_STAMP=".venv/flowline-requirements.sha"
REQ_SHA="$( (sha256sum requirements.txt 2>/dev/null || shasum -a 256 requirements.txt) | cut -d' ' -f1)"
if [[ "$(cat "$REQ_STAMP" 2>/dev/null)" != "$REQ_SHA" ]]; then
  say "Installing Python requirements (requirements.txt changed)…"
  .venv/bin/pip install -q -r requirements.txt && printf '%s' "$REQ_SHA" > "$REQ_STAMP"
fi
if [[ ! -d node_modules ]]; then
  command -v npm >/dev/null || die "Node.js 20+ is required."
  say "Installing Node packages (first run only)…"
  npm ci --no-audit --no-fund
fi
ok "Dependencies ready"

for port in "$API_PORT" "$WEB_PORT"; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    die "Port $port is already in use. Run ./stop.sh, or set API_PORT / WEB_PORT."
  fi
done

# ---------------------------------------------------------------- services
SERVICES="db"
if [[ -f osrm/alberta-latest.osrm.mldgr ]]; then
  SERVICES="db osrm"
elif [[ -f data/osm/alberta-latest.osm.pbf ]]; then
  say "Building OSRM routing data (one-time, ~5 minutes)…"
  if [[ "$DOCKER_MODE" == "sg" ]]; then sg docker -c "scripts/build_osrm.sh"; else scripts/build_osrm.sh; fi
  SERVICES="db osrm"
else
  warn "No OSM extract (data/osm/alberta-latest.osm.pbf): dispatch falls back to Mapbox / straight-line distance."
fi
say "Starting $SERVICES (docker compose)…"
dc up -d --wait $SERVICES
ok "Containers healthy: $SERVICES"

# ---------------------------------------------------------------- database
N_INCIDENTS="$("$PY" - <<'EOF' 2>/dev/null || echo 0
from core.env import load_dotenv
load_dotenv()
from core.pg import try_connect
conn = try_connect()
try:
    print(conn.execute("SELECT count(*) AS n FROM incidents").fetchone()["n"] if conn else 0)
except Exception:
    print(0)
EOF
)"
if [[ "${N_INCIDENTS:-0}" == "0" ]]; then
  CER="data/raw/pipeline-incidents-comprehensive-data.csv"
  if [[ ! -f "$CER" ]]; then
    say "Downloading CER incident data…"
    mkdir -p data/raw
    curl -sSL --fail -o "$CER" https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-comprehensive-data.csv
    curl -sSL --fail -o data/raw/pipeline-incidents-data-dictionary.csv \
      https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-data-dictionary.csv
  fi
  [[ -f data/processed/pipelines_ca.geojson ]] || "$PY" -m scripts.fetch_pipeline_systems || \
    warn "Could not fetch the national pipeline layer; using the bundled Alberta file."
  [[ -f data/processed/incident_weather.csv ]] || \
    warn "No weather data: similar-incident search runs without weather (python -m scripts.fetch_weather takes ~1 hour)."
  say "Loading the database…"
  "$PY" -m scripts.load_postgres
fi
ok "Database ready"

# ---------------------------------------------------------------- river crossings (map layer)
if [[ -f data/osm/alberta-latest.osm.pbf ]]; then
  HAS_CROSSINGS="$("$PY" - <<'PYEOF' 2>/dev/null || echo 0
from core.env import load_dotenv
load_dotenv()
from core.pg import try_connect
conn = try_connect()
sql = "SELECT to_regclass('public.waterway_crossings') IS NOT NULL AS ok"
print(int(bool(conn and conn.execute(sql).fetchone()["ok"])))
PYEOF
)"
  if [[ "$HAS_CROSSINGS" != "1" ]]; then
    say "Building the river-crossings map layer from the OSM extract (one-time, a few minutes)…"
    if "$PY" -m scripts.washout_crossings --layer-only >logs/crossings.log 2>&1; then
      ok "River-crossings layer built ($(tail -1 logs/crossings.log))"
    else
      warn "River-crossings layer not built; see logs/crossings.log (the map works without it)."
    fi
  fi
fi

# ---------------------------------------------------------------- app
# Rebuild only when something baked into the bundle changed: NEXT_PUBLIC_* values in
# .env.local, dependencies, config, or frontend sources. (No server is running here —
# the port check above guarantees it — so a rebuild can never leave a stale page live.)
build_stamp() {
  {
    cat .env.local package-lock.json next.config.ts postcss.config.mjs tsconfig.json 2>/dev/null
    find app components lib public -type f -print0 2>/dev/null | sort -z | xargs -0 sha256sum
  } | sha256sum | cut -d' ' -f1
}
STAMP_FILE=".next/flowline-build-stamp"
STAMP="$(build_stamp)"
if [[ "${FORCE_BUILD:-0}" == "1" || ! -f .next/BUILD_ID || "$(cat "$STAMP_FILE" 2>/dev/null)" != "$STAMP" ]]; then
  say "Building the web app (production; .env.local or frontend changed)…"
  npm run build >logs/web-build.log 2>&1 || die "Web build failed — see logs/web-build.log"
  echo "$STAMP" > "$STAMP_FILE"
else
  ok "Web build is up to date (.env.local and frontend unchanged)"
fi

say "Starting API on :$API_PORT and web app on :$WEB_PORT…"
nohup .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port "$API_PORT" --workers 1 \
  >logs/api.log 2>&1 &
echo $! > .run/api.pid
# Run next directly (not via npx) so the recorded pid is the server itself.
nohup node_modules/.bin/next start -p "$WEB_PORT" >logs/web.log 2>&1 &
echo $! > .run/web.pid

for _ in $(seq 1 90); do
  if curl -sf -o /dev/null "http://127.0.0.1:$API_PORT/health" && curl -sf -o /dev/null "http://127.0.0.1:$WEB_PORT/"; then
    ok "Flowline is up: http://localhost:$WEB_PORT  (API http://127.0.0.1:$API_PORT/docs)"
    if [[ $OPEN_BROWSER == 1 ]]; then
      (command -v xdg-open >/dev/null && xdg-open "http://localhost:$WEB_PORT" >/dev/null 2>&1) ||
        (command -v open >/dev/null && open "http://localhost:$WEB_PORT") || true
    fi
    exit 0
  fi
  sleep 1
done
die "Timed out waiting for the API or web app — see logs/api.log and logs/web.log"
