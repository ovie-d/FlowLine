# Flowline API for free hosting (Render free web service, 512 MB). No database or router
# inside: the database is Neon (free Postgres with PostGIS + pgvector) and routing uses the
# public OSRM server. Build context: the repository root.
FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY deploy/free/requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt
COPY api api
COPY core core
COPY models models
COPY data/cer_pipeline_incidents_alberta_2015.csv data/cer_pipeline_systems.csv data/

# Online-demo defaults; DATABASE_URL and GEMINI_API_KEY are set as secrets on the host.
ENV FLOWLINE_DEMO=1 \
    DECISIONS_BACKEND=postgres \
    OSRM_URL=https://router.project-osrm.org \
    GEMINI_MODEL=gemini-3.1-flash-lite \
    AI_PROMPTS_PER_VISITOR=3 \
    AI_DAILY_BUDGET_USD=1.0 \
    AGENT_BUDGET_USD=30
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
