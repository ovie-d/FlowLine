#!/usr/bin/env bash
# First-run extras, started in the background by start.sh so the app opens first:
#   1. download the Alberta OSM extract (Geofabrik, ~350 MB) if it is missing
#   2. build the OSRM routing data (~5 min) and start the router
#   3. build the river-crossings map layer (~2 min)
# Until step 2 finishes, dispatch uses straight-line distance with a warning that
# routing is still being prepared (.run/routing-building). Skip with FLOWLINE_ROUTING=0.
# Safe to interrupt: the download resumes and the build restarts on the next start.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY=".venv/bin/python"
PBF="data/osm/alberta-latest.osm.pbf"
URL="${OSM_EXTRACT_URL:-https://download.geofabrik.de/north-america/canada/alberta-latest.osm.pbf}"
MARKER=".run/routing-building"

log() { printf '%s %s\n' "$(date '+%H:%M:%S')" "$*"; }
in_docker_group() {
  if [[ "${DOCKER_MODE:-direct}" == "sg" ]]; then sg docker -c "$*"; else bash -c "$*"; fi
}

mkdir -p .run data/osm logs
trap 'rm -f "$MARKER"' EXIT
trap 'log "Interrupted; will continue on the next start."; exit 143' TERM INT

if [[ ! -f osrm/alberta-latest.osrm.mldgr ]]; then
  touch "$MARKER"
  if [[ ! -f "$PBF" ]]; then
    log "Downloading the Alberta OSM extract (~350 MB) from Geofabrik…"
    curl -fL --retry 3 --retry-delay 5 -C - -sS -o "$PBF.part" "$URL" || { log "Download failed."; exit 1; }
    if curl -fsSL -o "$PBF.md5" "$URL.md5"; then
      want="$(cut -d' ' -f1 < "$PBF.md5")"
      got="$("$PY" -c 'import hashlib,sys; h=hashlib.md5(); f=open(sys.argv[1],"rb"); [h.update(b) for b in iter(lambda: f.read(1<<20), b"")]; print(h.hexdigest())' "$PBF.part")"
      if [[ "$want" != "$got" ]]; then
        log "Checksum mismatch; deleting the partial download (it restarts next time)."
        rm -f "$PBF.part"
        exit 1
      fi
    fi
    mv "$PBF.part" "$PBF"
    log "Download complete."
  fi
  log "Building the OSRM routing data (one-time, ~5 minutes)…"
  in_docker_group "scripts/build_osrm.sh" || { log "OSRM build failed."; exit 1; }
  log "Starting the router…"
  in_docker_group "docker compose up -d --wait osrm" || { log "Router did not start."; exit 1; }
  rm -f "$MARKER"
  log "Road routing is ready (dispatch now uses drive times)."
fi

HAS_CROSSINGS="$("$PY" - <<'PYEOF' 2>/dev/null || echo 0
from core.env import load_dotenv
load_dotenv()
from core.pg import try_connect
conn = try_connect()
sql = "SELECT to_regclass('public.waterway_crossings') IS NOT NULL AS ok"
print(int(bool(conn and conn.execute(sql).fetchone()["ok"])))
PYEOF
)"
if [[ "$HAS_CROSSINGS" != "1" && -f "$PBF" ]]; then
  log "Building the river-crossings map layer (one-time, ~2 minutes)…"
  if "$PY" -m scripts.washout_crossings --layer-only; then
    log "River-crossings layer ready."
  else
    log "River-crossings layer not built (the map works without it)."
  fi
fi
log "Background setup finished."
