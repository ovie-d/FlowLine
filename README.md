# Flowline — Hazard Forecast

> *Their models tell you how strong the pipe is. Flowline tells you what kind of trouble
> to prepare for, and who to send.*

For any pipeline area and date, Flowline:

1. **Forecasts the mix of likely hazard types** (e.g. 36% ground movement & washout,
   19% incorrect operation, 14% equipment failure) from the whole industry's public
   Canada Energy Regulator (CER) incident history.
2. **Shows the most similar past incidents** as evidence (pgvector similarity, strictly
   before the forecast date).
3. **Maps each hazard to the crews and equipment** it needs (editable table — sample data
   until validated).
4. **Routes the matching crew** in an emergency by real drive time (local OSRM).
5. **Writes a short readiness briefing** with an AI agent (Gemini) that may only use
   numbers returned by Flowline's own tools — every number is checked.

The original corridor **Risk Ranking** (likelihood × consequence under an explicit policy)
and the **Decision Log** are kept as tabs.

> Forecasts are based on historical public incident data. Flowline supports engineering
> judgment; it does not certify any pipe as safe. It is an add-on to an operator's
> integrity models (QRA, Psqr, …), not a replacement.

**How good is it?** On 2022+ incidents it never saw, it clearly beats simple history
across Canada; in Alberta the gain is real but narrow; on NGTL alone it is not yet
distinguishable from simple history. Details: [`docs/MODEL_REPORT.md`](docs/MODEL_REPORT.md).

---

## Quick start (fresh clone)

Prerequisites: **Docker** (Desktop on macOS/Windows; engine + compose on Linux),
**Node.js 20+**, **Python 3.11+**, and ~2 GB free disk.

```bash
git clone https://github.com/ovie-d/FlowLine.git && cd FlowLine
git checkout hazard-forecast

# Optional but recommended: road routing data (~350 MB, Alberta)
mkdir -p data/osm
curl -L -o data/osm/alberta-latest.osm.pbf \
  https://download.geofabrik.de/north-america/canada/alberta-latest.osm.pbf

./start.sh            # Windows: powershell -ExecutionPolicy Bypass -File start.ps1
```

`start.sh` (and `start.ps1`) does everything, idempotently:

1. checks Docker is running (starts Docker Desktop on macOS/Windows),
2. creates `.env` / `.env.local` from `.env.example` if missing,
3. creates the Python venv and installs Node packages on first run,
4. builds the OSRM routing data once if the OSM extract is present (~5 min),
5. starts PostgreSQL + PostGIS + pgvector (and OSRM) with `docker compose`, waits for
   healthchecks,
6. loads the database if it is empty (downloads the CER CSVs if needed),
7. builds and starts the API (:8000) and web app (:3000), then opens
   <http://localhost:3000>.

Stop everything (data is kept): `./stop.sh` (Windows: `stop.ps1`).
Logs: `logs/api.log`, `logs/web.log`. The Windows scripts are syntax-checked but have not
been run on Windows yet.

### Data steps (what the launcher automates, for reference)

| Step | Command | Notes |
|---|---|---|
| CER incidents | downloaded to `data/raw/` | Open Government Licence – Canada |
| CER pipeline systems | `python -m scripts.fetch_pipeline_systems` | operator commodity + map layer |
| Weather (optional) | `python -m scripts.fetch_weather` | ECCC daily data, ~1 hour, resumable; used for similar incidents and context — **not** a model input |
| Routing (optional) | `scripts/build_osrm.sh` (`.ps1`) | needs `data/osm/alberta-latest.osm.pbf` |
| Database | `python -m scripts.load_postgres` | idempotent; never overwrites crew-table edits |
| Profile / evaluation | `python -m scripts.profile_cer`, `python -m scripts.evaluate` | writes `docs/DATA_PROFILE.md`, `docs/MODEL_REPORT.md`, `models/` |

The trained model (`models/hazard_forecast.*`, < 1 MB) is committed, so a fresh clone can
forecast without retraining.

---

## Environment variables

Backend — `.env` (never commit):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql://flowline:flowline@localhost:5432/flowline` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | docker compose credentials |
| `DECISIONS_BACKEND` | `postgres` (or `json` / `sqlite`) |
| `GEMINI_API_KEY` | AI briefing + chat. Empty = AI off; everything else works |
| `GEMINI_MODEL` | e.g. `gemini-3.1-flash-lite` (cheapest) or `gemini-3.5-flash-lite` |
| `AGENT_MAX_OUTPUT_TOKENS` / `AGENT_BUDGET_USD` | budget guard (default 800 / $15) |
| `OLLAMA_MODEL` / `OLLAMA_URL` | optional local fallback when Gemini is unreachable |
| `OSRM_URL` | default `http://localhost:5000` |
| `MAPBOX_TOKEN` | optional Directions fallback when OSRM is down; must not be URL-restricted |

Frontend — `.env.local`:

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | default `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Mapbox `pk.…` token (URL-restricted). Empty = offline Alberta map |
| `NEXT_PUBLIC_MAP_STYLE` | `dark` (default), `light-plus`, `outdoors`, `streets` |

---

## Offline demo checklist

| Works **without internet** | Needs internet |
|---|---|
| Hazard forecast, evidence, crews, crew editor | Mapbox basemap tiles (falls back to the offline Alberta map) |
| Map (offline Alberta view, incidents, pipelines, bases) | Open-Meteo weather outlook (panel shows "unavailable") |
| Emergency dispatch with OSRM drive times (Alberta) | Gemini briefing / chat (falls back to Ollama if `OLLAMA_MODEL` is set) |
| Risk Ranking, Decision Log, About this model | First-time downloads (CER data, OSM extract, Docker images, packages) |

Before going offline: run `./start.sh` once online, check the OSRM container is healthy
(`docker compose ps`), and make sure `data/osm/` and `osrm/` exist.

---

## Architecture

```
Next.js 16 (app/, components/command, components/ranking)  ── HTTP ──▶  FastAPI (api/)
                                                                             │
          core/: forecast · features · model (LightGBM + SHAP) · similar ◀───┤
                 readiness · crews · routing (OSRM → Mapbox → straight line) │
                 openmeteo · insights · agent/ (Gemini, tools, budget, numbers)
                                                                             │
PostgreSQL 18 + PostGIS + pgvector (docker)   OSRM (docker, Alberta car profile)
```

| Layer | Stack |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind 4, TanStack Query, Mapbox GL / react-map-gl, framer-motion |
| Backend | FastAPI, Pydantic, psycopg 3 |
| Model | LightGBM multiclass (8 hazard groups), prior-corrected, SHAP drivers |
| Data | PostgreSQL + PostGIS + pgvector, OSRM, ECCC weather, Open-Meteo |
| Agent | Google Gemini via `google-genai`, tool calls only, optional Ollama |

### API (main endpoints — interactive docs at `/docs`)

| Method | Path | What |
|---|---|---|
| `POST` | `/forecast` | Hazard mix for a point or corridor + date, drivers, evidence, low-evidence flag |
| `GET` | `/similar` | Similar past incidents (strictly before the date) |
| `GET` | `/readiness` | 7-day readiness: forecast, recommended crews + nearest base, weather, similar |
| `GET` / `PUT` | `/crews`, `/crews/map` | Crew & equipment table (sample until edited) |
| `POST` | `/dispatch/route` | Crew bases ranked by drive time, with route geometry |
| `POST` | `/briefing` | AI readiness briefing (numbers verified) |
| `GET` | `/model/info`, `/insights/washout` | Held-out performance; observed washout pattern |
| `GET` | `/agent/status`, `/agent/usage` | AI availability; token usage and spend |
| `GET` | `/ranking`, `/corridor/{name}`, `/triage`, `/decisions`, … | Existing ranking product |

---

## Tests

```bash
.venv/bin/pytest -q          # Postgres tests use a throwaway flowline_test database
npm run lint && npm run build
```

Tests never call a real LLM or touch your decision log or usage log.

---

## Docs

- [`docs/MODEL_REPORT.md`](docs/MODEL_REPORT.md) — honest evaluation (time split, rolling origin, baselines, ablations, operator check, where it fails)
- [`docs/DATA_PROFILE.md`](docs/DATA_PROFILE.md) — CER data profile, hazard taxonomy, leakage check of every candidate feature
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) · [`docs/QA_PREP.md`](docs/QA_PREP.md) — 5-minute demo and likely questions
- [`docs/WEATHER_COVERAGE.md`](docs/WEATHER_COVERAGE.md) · [`docs/WASHOUT_WATCH.md`](docs/WASHOUT_WATCH.md) · [`docs/research/`](docs/research/) · [`docs/BACKLOG.md`](docs/BACKLOG.md)
- [`HANDOFF.md`](HANDOFF.md) / [`CODING_GUIDELINES.md`](CODING_GUIDELINES.md) — original ranking product

## Data sources

Canada Energy Regulator — Pipeline Incident Data and Pipeline Systems layer (Open
Government Licence – Canada) · Environment and Climate Change Canada — Historical Climate
Data · © OpenStreetMap contributors (Geofabrik extract), routing via OSRM · Open-Meteo ·
Mapbox.

## License

Hackathon project · Tech Wolves · IEEE YP Industry Hackathon 2026.
