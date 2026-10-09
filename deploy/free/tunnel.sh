#!/usr/bin/env bash
# Laptop backup for demos: run the full online-demo container (database, own OSRM router,
# API, web; demo limits on) and share it through a free Cloudflare quick tunnel.
# Only works while this laptop is on; the https link changes each time.
#   deploy/free/tunnel.sh          start (prints the public link)
#   deploy/free/tunnel.sh stop     stop the container and the tunnel
# Needs the image from deploy/huggingface (built once with deploy/free/tunnel.sh build).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE=flowline-demo:local
NAME=flowline-demo
CF="$HOME/.local/bin/cloudflared"
dk() { if docker info >/dev/null 2>&1; then bash -c "$*"; else sg docker -c "$*"; fi; }

case "${1:-start}" in
  build)
    cd "$ROOT"
    .venv/bin/python deploy/huggingface/publish.py local bundle
    .venv/bin/python -c "import sys; sys.path.insert(0, 'deploy/huggingface'); import publish; publish.stage_space('local')"
    (cd deploy/huggingface/.bundle && python3 -m http.server 8765 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > /tmp/flowline-bundle-http.pid)
    trap 'kill "$(cat /tmp/flowline-bundle-http.pid)" 2>/dev/null || true' EXIT
    dk "docker build --network host --build-arg FLOWLINE_DATA_URL=http://127.0.0.1:8765 -t $IMAGE deploy/huggingface/.bundle/space"
    ;;
  stop)
    pkill -f "cloudflared tunnel --url http://localhost:7860" 2>/dev/null || true
    dk "docker rm -f $NAME" >/dev/null 2>&1 || true
    echo "Stopped."
    ;;
  start)
    if [[ ! -x "$CF" ]]; then
      echo "Downloading cloudflared (Cloudflare's official tunnel client) to $CF…"
      mkdir -p "$(dirname "$CF")"
      curl -fsSL -o "$CF" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
      chmod +x "$CF"
    fi
    dk "docker image inspect $IMAGE" >/dev/null 2>&1 || { echo "Build the image first: deploy/free/tunnel.sh build"; exit 1; }
    umask 077
    KEYFILE="$(mktemp)"
    grep '^GEMINI_API_KEY=' "$ROOT/.env" > "$KEYFILE" 2>/dev/null || true
    dk "docker rm -f $NAME >/dev/null 2>&1; docker run -d --name $NAME -p 127.0.0.1:7860:7860 --env-file $KEYFILE $IMAGE" >/dev/null
    rm -f "$KEYFILE"
    for _ in $(seq 1 60); do curl -sf -o /dev/null http://localhost:7860/api/health && break; sleep 1; done
    echo "Flowline demo running on http://localhost:7860. Opening a public tunnel…"
    nohup "$CF" tunnel --url http://localhost:7860 --no-autoupdate > /tmp/flowline-tunnel.log 2>&1 &
    for _ in $(seq 1 30); do
      link="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/flowline-tunnel.log | head -1 || true)"
      [[ -n "$link" ]] && break
      sleep 1
    done
    echo "Public link (share it; valid until you stop it): ${link:-see /tmp/flowline-tunnel.log}"
    ;;
esac
