# Flowline Hazard Forecast

**v2.1.0** · **[Try it online](https://a112358-flowline.hf.space)** · [Changelog](CHANGELOG.md) · [Model report](docs/MODEL_REPORT.md)

> *Their models tell you how strong the pipe is. Flowline tells you what kind of trouble
> to prepare for, and who to send.*

![Flowline forecasting the hazard mix around Edson, Alberta: map of past incidents by hazard type on the left, forecast bars and similar past incidents on the right](docs/images/flowline-hazard-forecast.png)

Flowline is a readiness tool for pipeline operators. For any pipeline area and week, it
**forecasts the mix of hazard types** likely behind an incident there. The forecast comes
from the industry's public Canada Energy Regulator (CER) incident history, and Flowline
shows the evidence behind it. It then turns the forecast into action: which crews and
equipment to have ready, and in an emergency, which crew base to send by real drive time.

> Forecasts are based on historical public incident data. Flowline supports engineering
> judgment; it does not certify any pipe as safe. It is an add-on to an operator's
> integrity models (QRA, Psqr, …), not a replacement.

---

## Try it online (no install)

Open **<https://a112358-flowline.hf.space>**. It's the full app in your browser: forecast, evidence,
readiness, emergency dispatch with real drive times, the maps, and the AI briefing.

- **AI limit:** it's a free demo by a student team, so each visitor gets **3 AI prompts
  per day**. A daily budget cap keeps costs predictable; everything else is unlimited.
- **Private edits:** your crew-table edits and decisions stay private to your browser for
  24 hours. Everyone else sees the clean demo data.
- **Waking up:** it's hosted for free on Hugging Face Spaces. If nobody has visited for
  two days it sleeps, and the first visit wakes it, which can take a minute or two.

---

## Try it in 2 minutes

Copy one line into a terminal. It checks what you have and **offers to install anything
missing**: it shows the exact commands and asks first. Then it downloads Flowline into
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
./start.sh                       # Windows: powershell -ExecutionPolicy Bypass -File start.ps1
```

Stop everything with `./stop.sh` (Windows: `stop.ps1`). Your data is kept.

### Prerequisites

The installer offers to install any of these that are missing (with your permission;
it may ask for your password). You can also install them yourself:

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

### What the first run does

- **Setup:** installs the Python and Node packages into the Flowline folder (nothing
  system-wide), builds the database from the public CER incident data, builds the web app
  and opens it.
- **Time:** on a test machine that already had the packages and Docker images cached, it
  was ready in under 2 minutes. A fresh machine also downloads about 1.4 GB of packages and
  builds the database image (about 0.7 GB), so expect longer, depending on your connection.
- **Road routing** for emergency dispatch is prepared in the background. The Alberta
  OpenStreetMap extract (~350 MB) is downloaded and the router is built, about 5–10 more
  minutes. Until then, dispatch shows straight-line distance with a "routing is still
  being prepared" warning.
- **Later starts** take under a minute.

### No keys needed

- **Map:** the installer asks for an optional Mapbox token (free at mapbox.com). Press
  Enter to use the interactive open basemaps instead (OpenFreeMap dark/light/streets, Esri
  satellite imagery); all map features work either way.
- **AI readiness briefing:** works without a key, through the online demo (3 prompts per
  day). Add your own `GEMINI_API_KEY` to `.env` for unlimited use.
- **Everything else** (forecast, evidence, crews, dispatch, ranking) works without keys.

### Desktop app

A window with the Flowline icon. It runs the same launcher, waits until everything is
healthy, opens the app, and stops everything when you close it. Docker is still required.

- **Linux:** download the AppImage from the
  [v2.0.0 release](https://github.com/ovie-d/FlowLine/releases/tag/v2.0.0), or build it
  with `cd desktop && npm ci && npm run dist`. Then run `desktop/install-linux.sh --desktop`
  to add it to your app menu and desktop. Distros without `libfuse2` are handled.
- **Windows (.exe) and macOS (.dmg):** built by GitHub Actions, **unsigned and untested**.
  [desktop/README.md](desktop/README.md) explains how to get past SmartScreen and
  Gatekeeper.

---

## Features

- **Hazard forecast:** the probability of each of 8 hazard groups (corrosion & cracking,
  equipment failure, incorrect operation, third-party damage, ground movement & washout,
  natural forces, construction & material, fire / ignition) for a point or area and a date.
  - Each bar shows its main drivers (SHAP) and how it compares with the Alberta average.
  - A low-evidence warning appears when there is little nearby history.
  - Probabilities above 50% are labelled "lower certainty", because the model was
    overconfident there on held-out data.
- **Evidence:** the most similar past incidents (pgvector), strictly before the forecast
  date, with their CER cause codes in plain English.
- **Readiness:** recommended crews and equipment for the likely hazards, the nearest crew
  base by drive time, and the 7-day weather outlook (context only, not a model input).
  The crew table is editable and marked *sample — to be validated* until an operator
  replaces it.
- **Emergency dispatch:** drop a pin or search. Flowline ranks crew bases by real drive
  time (local OSRM on OpenStreetMap), draws every route, and handles an off-road last mile
  separately.
  - A response timeline replays the drive. It is labelled **simulation**: only the drive
    time is real.
  - It includes an equipment checklist and a printable one-page summary.
- **Interactive map:**
  - Basemaps: dark, light, streets and satellite; 3D terrain; a globe view.
  - Layers: incidents (clustered), heatmap, pipelines, crew bases, river crossings.
  - Click an incident for its details; a year slider replays the history.
  - An offline Alberta map is used when WebGL is unavailable.
- **AI readiness briefing** (optional, Gemini): a short briefing written only from
  Flowline's own tool results. Every number in it is checked against those results.
- **Risk Ranking & Decision Log** (from v1): corridor ranking under an explicit
  likelihood × consequence policy, agent drafts, and a decision log.
- Dark and light themes, accessible contrast (WCAG AA), and layouts from laptop to wide
  screens.

---

## How good is the forecast?

The full results are in [`docs/MODEL_REPORT.md`](docs/MODEL_REPORT.md).

**Setup.** LightGBM multiclass model trained on CER incidents up to 2021 and tested on
2022+ incidents it never saw. It was compared with simple baselines (national, provincial
and local history), with 95% bootstrap confidence intervals.

- **Across Canada (n = 430):** it clearly beats the best simple baseline. Log loss
  improves by 0.154 [0.109, 0.198], and the true hazard is in its top 3 for 72% of
  incidents.
- **In Alberta (n = 164):** the gain is real but narrow: log loss improves by 0.081
  [0.022, 0.139].
- **On NGTL alone (n = 122):** the model is **not yet distinguishable** from simple
  history (Δ log loss −0.037 [−0.107, +0.028]). Public data isn't enough for a single
  operator's network. Operator incident data would be needed to do better.
- **Earlier years:** the rolling-origin check (each year 2020–2025 trained only on the years
  before it) shows a gain in most years. 2024 is not distinguishable from the baseline.

**Honest limitations:**

- Public CER data has cause codes only, no incident narratives.
- Rare hazards are forecast poorly: third-party damage, fire / ignition, and construction
  & material defects.
- Above 50%, probabilities were overconfident, so the app doesn't show an exact number
  there.
- Weather made no measurable difference, so it is shown as context, not used as a model
  input.
- The post-2022 rise in Alberta washouts is shown as an observed pattern, not a forecast.
- Crew bases, crew types and equipment are sample data until an operator validates them.

---

## Architecture

```
Next.js 16 (app/, components/)  ── HTTP ──▶  FastAPI (api/)
                                                  │
   core/: forecast · features · model (LightGBM + SHAP) · similar (pgvector)
          readiness · crews · routing (OSRM → Mapbox → straight line)
          mapdata · insights · agent/ (Gemini, tools, budget, number check)
                                                  │
   PostgreSQL 18 + PostGIS + pgvector (Docker)    OSRM (Docker, Alberta car profile)
```

| Layer | Stack |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind 4, TanStack Query, react-map-gl (Mapbox GL or MapLibre GL), framer-motion |
| Backend | FastAPI, Pydantic, psycopg 3 |
| Model | LightGBM multiclass (8 hazard groups), prior-corrected, SHAP drivers |
| Data | PostgreSQL + PostGIS + pgvector, OSRM, ECCC weather, Open-Meteo |
| Agent | Google Gemini via `google-genai`, tool calls only, optional local Ollama |
| Desktop | Electron (Linux AppImage; Windows/macOS via GitHub Actions) |

<details>
<summary>API endpoints (interactive docs at <code>http://127.0.0.1:8000/docs</code>)</summary>

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
| `GET` | `/ranking`, `/corridor/{name}`, `/triage`, `/decisions`, … | Risk Ranking and Decision Log |

</details>

<details>
<summary>Configuration (<code>.env</code> and <code>.env.local</code>; created on first run, never committed)</summary>

Backend: `.env`

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql://flowline:flowline@localhost:5432/flowline` (local dev default) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | docker compose credentials |
| `DECISIONS_BACKEND` | `postgres` (or `json` / `sqlite`) |
| `GEMINI_API_KEY` | AI briefing + chat. Empty = AI off; everything else works |
| `GEMINI_MODEL` | e.g. `gemini-3.1-flash-lite` or `gemini-3.5-flash-lite` |
| `AGENT_MAX_OUTPUT_TOKENS` / `AGENT_BUDGET_USD` | budget guard (default 800 / $15) |
| `OLLAMA_MODEL` / `OLLAMA_URL` | optional local fallback when Gemini is unreachable |
| `OSRM_URL` | default `http://localhost:5000` |
| `MAPBOX_TOKEN` | optional Directions fallback when OSRM is down; must not be URL-restricted |
| `FLOWLINE_REMOTE_AI` | AI briefing/chat through the online demo when there's no local key (default: the Flowline demo; empty = off) |
| `FLOWLINE_DEMO`, `AI_PROMPTS_PER_VISITOR`, `AI_DAILY_BUDGET_USD` | online-demo mode: per-visitor sandbox, 3 AI prompts per visitor per day, daily spend cap (website only) |

Frontend: `.env.local`

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | default `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Mapbox `pk.…` token (URL-restricted). Empty = keyless open basemaps |
| `NEXT_PUBLIC_MAP_STYLE` | Risk Ranking map with Mapbox: `dark` (default), `light-plus`, `outdoors`, `streets` |

Launcher options: `FLOWLINE_ROUTING=0` skips the background routing setup; `API_PORT` /
`WEB_PORT` change the ports; `FORCE_BUILD=1` rebuilds the web app.

</details>

<details>
<summary>What <code>start.sh</code> does, and offline use</summary>

`start.sh` (Windows: `start.ps1`) is idempotent; run it any time:

1. checks Docker is running (starts Docker Desktop on macOS/Windows),
2. creates `.env` / `.env.local` from `.env.example` if missing (no keys needed),
3. creates the Python venv and installs Node packages on first run (re-installs when
   `requirements.txt` changes),
4. starts PostgreSQL + PostGIS + pgvector (and OSRM once its data exists) with
   `docker compose`, and waits for the healthchecks,
5. loads the database if it is empty (downloads the CER data if needed),
6. starts the background setup if routing or the river-crossings layer is missing (log in
   `logs/background-setup.log`),
7. builds the web app when anything baked into it changed, starts the API (:8000) and the
   web app (:3000), then opens <http://localhost:3000>.

**Offline:** after one online start, the forecast, evidence, crews, dispatch (OSRM),
ranking and decision log work without internet. Basemaps, the weather outlook and the
Gemini briefing need a connection; the map falls back to the offline Alberta view.

**Windows:** `start.ps1`, `stop.ps1` and `install.ps1` are syntax-checked and partly
exercised with PowerShell 7 on Linux, but **haven't been run on Windows yet**.

</details>

---

## Development

```bash
.venv/bin/pytest -q            # Python tests (Postgres tests use a throwaway flowline_test DB)
npm run lint && npm run build  # frontend
python -m scripts.evaluate     # re-run the evaluation; rewrites docs/MODEL_REPORT.md
```

Tests never call a real LLM or touch your decision log or usage log. `AGENTS.md` has the
architecture and the project rules: no invented numbers, leakage guards, and never tuning
on the 2022+ test set.

**Docs:**

- [`docs/MODEL_REPORT.md`](docs/MODEL_REPORT.md): evaluation (time split, rolling origin,
  baselines, ablations, operator check, where it fails).
- [`docs/DATA_PROFILE.md`](docs/DATA_PROFILE.md): CER data profile, hazard taxonomy, and
  a leakage check of every candidate feature.
- [`docs/WEATHER_COVERAGE.md`](docs/WEATHER_COVERAGE.md) and
  [`docs/WASHOUT_WATCH.md`](docs/WASHOUT_WATCH.md): the weather and washout experiments.
- [`docs/research/TSB_NARRATIVES.md`](docs/research/TSB_NARRATIVES.md): whether public
  TSB narratives could be used.
- [`desktop/README.md`](desktop/README.md): the desktop app.
- [`deploy/huggingface/README.md`](deploy/huggingface/README.md): how the online demo is
  built and deployed (one container on Hugging Face Spaces).
- [`legacy/v1/`](legacy/v1/): the original v1 hackathon build.

---

## Data sources and licences

| Source | Used for | Licence / terms |
|---|---|---|
| [Canada Energy Regulator](https://www.cer-rec.gc.ca/en/safety-environment/industry-performance/interactive-pipeline/): Pipeline Incident Data, Pipeline Systems | Incidents, hazard labels, pipeline map | [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada) |
| [Environment and Climate Change Canada](https://climate.weather.gc.ca/): Historical Climate Data | Weather context, similar-incident search | Open Government Licence – Canada |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) via [Geofabrik](https://download.geofabrik.de/) | Road routing, river crossings | ODbL, © OpenStreetMap contributors |
| [OSRM](https://project-osrm.org/) | Drive times | BSD 2-Clause |
| [Open-Meteo](https://open-meteo.com/) | 7-day weather outlook | CC BY 4.0 |
| [OpenFreeMap](https://openfreemap.org/) (OpenMapTiles schema) | Keyless basemaps | Free to use; OSM data under ODbL |
| [Esri World Imagery](https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9) | Keyless satellite basemap | Esri terms of use, with attribution |
| [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) | Keyless 3D terrain | Open data; attribution per source |
| [Mapbox](https://www.mapbox.com/legal/tos) (optional) | Basemaps with a token | Mapbox terms of service |

The keyless basemap services are free with fair-use limits. Check their terms before a
large production deployment.

---

## Credits

Built by the **Tech Wolves** team for the IEEE Young Professionals Industry Hackathon
2026 (Energy & Infrastructure, Case 10), and carried on from there.

- **Special thanks to David ([@ovie-d](https://github.com/ovie-d))** for the original v1
  build: the scoring core, the agent and the decision log. Everything in v2 stands on that
  foundation, and he worked incredibly hard on it. The v1 plan and code are kept in
  [`legacy/v1/`](legacy/v1/).
- Thanks to **[@jafar3073](https://github.com/jafar3073)** and the whole **Tech Wolves**
  team.
- v2.0 (Hazard Forecast, dispatch, maps, installers and desktop app):
  [@aabceh112358](https://github.com/aabceh112358).

## License

No open-source licence has been chosen yet. Until one is added, all rights are reserved
by the authors. The data sources above keep their own licences.
