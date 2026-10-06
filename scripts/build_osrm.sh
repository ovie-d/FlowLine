#!/usr/bin/env bash
# One-time OSRM preprocessing (car profile, MLD pipeline) of the Alberta extract.
# Input:  data/osm/alberta-latest.osm.pbf  (Geofabrik)
# Output: osrm/alberta-latest.osrm*        (git-ignored; served by docker compose "osrm")
# Usage:  scripts/build_osrm.sh [--force]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:v26.10.0-debian}"
PBF="$ROOT/data/osm/alberta-latest.osm.pbf"
OUT="$ROOT/osrm"
BASE="alberta-latest"
THREADS="${OSRM_THREADS:-4}"

if [[ ! -f "$PBF" ]]; then
  echo "Missing $PBF — download it from https://download.geofabrik.de/north-america/canada/alberta-latest.osm.pbf" >&2
  exit 1
fi
if [[ -f "$OUT/$BASE.osrm.mldgr" && "${1:-}" != "--force" ]]; then
  echo "OSRM data already built in $OUT (use --force to rebuild)."
  exit 0
fi

mkdir -p "$OUT"
# Hard-link (or copy) the extract next to the outputs; OSRM writes beside its input.
ln -f "$PBF" "$OUT/$BASE.osm.pbf" 2>/dev/null || cp "$PBF" "$OUT/$BASE.osm.pbf"

run() { docker run --rm -v "$OUT:/data" "$IMAGE" "$@"; }

echo "[1/3] osrm-extract (car profile)…"
run osrm-extract -p /opt/car.lua -t "$THREADS" "/data/$BASE.osm.pbf"
echo "[2/3] osrm-partition…"
run osrm-partition -t "$THREADS" "/data/$BASE.osrm"
echo "[3/3] osrm-customize…"
run osrm-customize -t "$THREADS" "/data/$BASE.osrm"

rm -f "$OUT/$BASE.osm.pbf"
echo "Done. Start the router with: docker compose up -d osrm"
