# FlowLine — Tech Wolves · Case 10

IEEE YP Industry Hackathon · Energy & Infrastructure  
**Pipeline Incident Risk Agent** — Next.js dashboard + FastAPI + `core/` scoring

## Setup

### Frontend (Next.js)

```bash
npm install
cp .env.example .env.local
# edit .env.local:
#   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
#   NEXT_PUBLIC_MAPBOX_TOKEN=pk.…   # paste your Mapbox public token
npm run dev
# http://localhost:3000
```

Restart `npm run dev` after changing `.env.local`. Without a Mapbox token, the map tab uses the offline SVG view.

### Backend (FastAPI + core)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# API (one worker — keeps agent sessions + decisions consistent)
uvicorn api.main:app --reload --workers 1
# http://127.0.0.1:8000/health
# http://127.0.0.1:8000/docs

# Required Case deliverables
python -m core.deliverables

# Tests
pytest -q
```

Seed data: `data/cer_pipeline_incidents_alberta_2015.csv`

## Honesty

We rank historic incident hotspots under an explicit risk policy.  
We do **not** certify any pipe as safe. The tool supports the integrity
engineer's decision; it doesn't replace engineering judgment.

See `HANDOFF.md` and `CODING_GUIDELINES.md`.
