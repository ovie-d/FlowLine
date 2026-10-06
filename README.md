# Flowline — Hazard Forecast

> *Their models tell you how strong the pipe is. Flowline tells you what kind of trouble
> to prepare for, and who to send.*

## Try it in 2 minutes

Copy one line into a terminal. It checks what you have, downloads Flowline into
`~/flowline` and starts it at <http://localhost:3000>. **No keys or accounts needed.**

**Linux / macOS** (Terminal):

```bash
curl -fsSL https://raw.githubusercontent.com/ovie-d/FlowLine/main/install.sh | bash
```

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/ovie-d/FlowLine/main/install.ps1 | iex
```

**Prefer not to pipe scripts from the internet?** (Common on managed work laptops.) Do the
same by hand. You can read [`install.sh`](install.sh) / [`install.ps1`](install.ps1) and
[`start.sh`](start.sh) first:

```bash
git clone https://github.com/ovie-d/FlowLine.git flowline && cd flowline
./start.sh                                    # Windows: powershell -ExecutionPolicy Bypass -File start.ps1
```

**Prerequisites** (install these yourself; the installer links to each one if missing):

| | Linux | macOS | Windows |
|---|---|---|---|
| Docker | [Docker Engine](https://docs.docker.com/engine/install/) + your user in the `docker` group | [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) | [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) (WSL 2) |
| git | package manager | `xcode-select --install` | [git for Windows](https://git-scm.com/download/win) |
| Node.js 20+ | [nodejs.org](https://nodejs.org/en/download) | [nodejs.org](https://nodejs.org/en/download) | [nodejs.org](https://nodejs.org/en/download) |
| Python 3.11+ | with `venv` (`python3-venv` on Debian/Ubuntu) | [python.org](https://www.python.org/downloads/) | [python.org](https://www.python.org/downloads/windows/) (with the `py` launcher) |

About 5 GB free disk (packages, Docker images, database, routing data).

> **Docker Desktop licensing.** Docker Desktop is free for personal use, education,
> non-commercial open source and small businesses, but **companies with more than 250
> employees or more than US$10 million annual revenue need a paid Docker subscription**.
> On corporate machines, check with IT before installing it. Docker Engine on Linux is
> free (open source).

**What the first run does.** It installs the Python and Node packages into the folder
(nothing system-wide), builds the database from the public CER incident data, builds the
web app and opens it. On a test machine that already had the packages and Docker images
cached, it was ready in **under 2 minutes**. A fresh machine also downloads the Python and
Node packages (about 1.4 GB installed) and builds the database image (about 0.7 GB), so
expect it to take longer, depending on your connection. Road routing for emergency dispatch is prepared
**in the background**: the Alberta OpenStreetMap extract (~350 MB) is downloaded and the
router is built in about 5–10 more minutes. Until then, dispatch shows straight-line
distance with a "routing is still being prepared" warning. Later starts take under a
minute.

**Without any keys:**

- **Map:** interactive WebGL map on open basemaps (OpenFreeMap dark/light/streets, Esri
  satellite imagery). A Mapbox token in `.env.local` switches to Mapbox styles.
- **AI readiness briefing:** off, with a message saying why. Add a `GEMINI_API_KEY` in
  `.env` to turn it on.
- **Everything else** (forecast, evidence, crews, dispatch, ranking) works without keys.

**Before this is merged into `main`**, test the PR branch with
`curl -fsSL https://raw.githubusercontent.com/ovie-d/FlowLine/hazard-forecast/install.sh | FLOWLINE_BRANCH=hazard-forecast bash`
(Windows: set `$env:FLOWLINE_BRANCH = "hazard-forecast"` and use the `hazard-forecast`
URL).

**Desktop app.** A window with the Flowline icon that runs the same launcher and stops
everything when closed: see [Desktop app](#desktop-app-linux-first) below. Windows and macOS
builds come from GitHub Actions and are unsigned and untested.

---

## What Flowline does

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

## What `start.sh` does

`start.sh` (Windows: `start.ps1`) is idempotent. Run it any time:

1. checks Docker is running (starts Docker Desktop on macOS/Windows),
2. creates `.env` / `.env.local` from `.env.example` if missing (no keys needed),
3. creates the Python venv and installs Node packages on first run (re-installs when
   `requirements.txt` changes),
4. starts PostgreSQL + PostGIS + pgvector (and OSRM once its data exists) with
   `docker compose`, and waits for the healthchecks,
5. loads the database if it is empty (downloads the CER CSVs if needed),
6. starts the background setup if routing or the river-crossings layer is missing
   (`scripts/background_setup.sh`, log in `logs/background-setup.log`; `FLOWLINE_ROUTING=0`
   skips it),
7. builds the web app when anything baked into it changed, starts the API (:8000) and the
   web app (:3000), then opens <http://localhost:3000>.

Stop everything (data is kept): `./stop.sh` (Windows: `stop.ps1`). This also pauses an
unfinished background setup, which resumes on the next start.
Logs: `logs/api.log`, `logs/web.log`, `logs/background-setup.log`. The Windows scripts are
syntax-checked and partly exercised with PowerShell 7 on Linux, but **have not been run on
Windows yet**.

### Data steps (what the launcher automates, for reference)

| Step | Command | Notes |
|---|---|---|
| CER incidents | downloaded to `data/raw/` | Open Government Licence – Canada |
| CER pipeline systems | `python -m scripts.fetch_pipeline_systems` | operator commodity + map layer |
| Weather (optional) | `python -m scripts.fetch_weather` | ECCC daily data, ~1 hour, resumable; used for similar incidents and context — **not** a model input |
| Routing (optional) | `scripts/build_osrm.sh` (`.ps1`) | needs `data/osm/alberta-latest.osm.pbf` |
| River crossings (optional) | `python -m scripts.washout_crossings --layer-only` | same OSM extract; map layer only |
| Database | `python -m scripts.load_postgres` | idempotent; never overwrites crew-table edits |
| Profile / evaluation | `python -m scripts.profile_cer`, `python -m scripts.evaluate` | writes `docs/DATA_PROFILE.md`, `docs/MODEL_REPORT.md`, `models/` |

The trained model (`models/hazard_forecast.*`, < 1 MB) is committed, so a fresh clone can
forecast without retraining.

### Desktop app (Linux first)

`desktop/` wraps the app in its own window (Electron, Flowline icon). It runs the same
launcher, waits for the health checks, opens the window, and stops everything when you
close it. **Docker is still required.**

```bash
cd desktop && npm ci && npm run dist   # → desktop/dist/Flowline-<version>-x86_64.AppImage
./install-linux.sh                     # optional: add it to the desktop menu
```

WebGL is forced on (GPU blocklist ignored, software fallback allowed). Details, the
`libfuse2` note and what Windows/macOS still need are in [desktop/README.md](desktop/README.md).

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
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Mapbox `pk.…` token (URL-restricted). Empty = keyless open basemaps (MapLibre; OpenFreeMap + Esri imagery) |
| `NEXT_PUBLIC_MAP_STYLE` | Risk Ranking map only: `dark` (default), `light-plus`, `outdoors`, `streets` |

The forecast and dispatch maps have their own **Map & layers** panel: basemap (Auto follows
the dark/light theme; Dark, Light, Streets, Satellite), 3D terrain, globe when zoomed out,
and layers (incidents, heatmap, pipelines, crew bases, river crossings). The river-crossings
layer is built by `start.sh` on first run when the OSM extract is present (about two
minutes; `python -m scripts.washout_crossings --layer-only` does the same by hand); without
the extract the panel says so. Theme and map choices are remembered per browser.

---

## Offline demo checklist

| Works **without internet** | Needs internet |
|---|---|
| Hazard forecast, evidence, crews, crew editor | Basemaps, Mapbox or open (offline, the map falls back to the offline Alberta view with the same layers) |
| Map layers (incidents, pipelines, bases, routes) | Open-Meteo weather outlook (panel shows "unavailable") |
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
| `GET` | `/map/incidents`, `/map/incidents/{id}` | Incident points; one incident with plain-English CER cause codes |
| `GET` | `/map/pipelines`, `/map/crossings` | Pipeline systems; pipeline–waterway crossings (display only) |
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
