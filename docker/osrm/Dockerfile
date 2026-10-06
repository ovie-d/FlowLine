# OSRM router (MLD) + curl for the compose healthcheck.
FROM ghcr.io/project-osrm/osrm-backend:v26.10.0-debian

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
