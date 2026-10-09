# syntax=docker/dockerfile:1
# Flowline online demo: one container with PostgreSQL + PostGIS + pgvector, the OSRM
# router, the FastAPI backend and the Next.js app (served on port 7860).
# Built on Hugging Face Spaces from deploy/huggingface/publish.sh; the database snapshot
# and the routing graph come from the public dataset repo in FLOWLINE_DATA_URL.

FROM ghcr.io/project-osrm/osrm-backend:v26.10.0-debian AS osrm
FROM node:22-trixie-slim AS node

FROM postgis/postgis:18-3.6
ARG FLOWLINE_DATA_URL
ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/usr/lib/postgresql/18/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    NEXT_TELEMETRY_DISABLED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-18-pgvector python3 python3-venv \
    curl ca-certificates zstd libgomp1 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=osrm /usr/local/bin/osrm-routed /usr/local/bin/osrm-routed
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# Hugging Face runs the container as uid 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user
WORKDIR /home/user/app

COPY --chown=user requirements.txt ./
RUN python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
COPY --chown=user package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY --chown=user . .

# Web app: the browser calls /api on the same address; Next forwards it to FastAPI.
# The Mapbox token is an optional build secret (restrict it to the Space's domain).
RUN --mount=type=secret,id=NEXT_PUBLIC_MAPBOX_TOKEN,mode=0444,required=false \
    NEXT_PUBLIC_MAPBOX_TOKEN="$(cat /run/secrets/NEXT_PUBLIC_MAPBOX_TOKEN 2>/dev/null || true)" \
    NEXT_PUBLIC_API_URL=/api FLOWLINE_API_PROXY=http://127.0.0.1:8000 \
    npm run build

# Routing graph and database snapshot, restored into the image so startup is instant.
RUN test -n "$FLOWLINE_DATA_URL" \
 && mkdir -p osrm \
 && curl -fsSL "$FLOWLINE_DATA_URL/osrm-alberta.tar.zst" | tar --zstd -x -C osrm \
 && curl -fsSL -o /tmp/flowline-db.dump "$FLOWLINE_DATA_URL/flowline-db.dump" \
 && deploy/huggingface/init_db.sh /tmp/flowline-db.dump \
 && rm /tmp/flowline-db.dump

ENV DATABASE_URL=postgresql://flowline@127.0.0.1:5432/flowline \
    DECISIONS_BACKEND=postgres \
    OSRM_URL=http://127.0.0.1:5000 \
    FLOWLINE_DEMO=1 \
    GEMINI_MODEL=gemini-3.1-flash-lite \
    AI_PROMPTS_PER_VISITOR=3 \
    AI_DAILY_BUDGET_USD=1.0 \
    AGENT_BUDGET_USD=30

EXPOSE 7860
ENTRYPOINT []
CMD ["deploy/huggingface/run.sh"]
