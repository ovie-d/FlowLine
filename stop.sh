#!/usr/bin/env bash
# Stop everything started by ./start.sh (web app, API, containers). Data is kept.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Stop a process and all its descendants (background setup runs curl / docker children).
kill_tree() {
  local child
  for child in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$child"; done
  kill -TERM "$1" 2>/dev/null
}
if [[ -f .run/setup.pid ]]; then
  pid="$(cat .run/setup.pid)"
  if kill -0 "$pid" 2>/dev/null; then
    kill_tree "$pid" && echo "stopped background setup ($pid); it resumes on the next start"
  fi
  rm -f .run/setup.pid .run/routing-building
fi

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
