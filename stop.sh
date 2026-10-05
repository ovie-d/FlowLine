#!/usr/bin/env bash
# Stop everything started by ./start.sh (web app, API, containers). Data is kept.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for name in web api; do
  pidfile=".run/$name.pid"
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    # Stop the process and its children (npx spawns next-server).
    pkill -TERM -P "$pid" 2>/dev/null
    kill -TERM "$pid" 2>/dev/null && echo "stopped $name ($pid)"
    rm -f "$pidfile"
  fi
done

if docker info >/dev/null 2>&1; then
  docker compose stop
elif id -nG "$USER" 2>/dev/null | grep -qw docker; then
  sg docker -c "docker compose stop"
else
  echo "Docker not accessible; containers left as they are."
fi
echo "Flowline stopped (database volume and OSRM data are kept)."
