# BUILD_PROMPT.md — Flowline Hazard Forecast

You are Claude Code working in the FlowLine repository. Read this whole file before doing anything. Work through the phases in order. **Stop at every `STOP & REPORT` checkpoint**, summarize what you did and found, and wait for my approval before continuing.

---

## 0. Context (read first)

### What exists today
FlowLine was built at the IEEE YP Industry Hackathon (Case 10). It ranks Alberta pipeline corridors by risk = likelihood × consequence using a 313-row CER sample, with a policy slider, a Claude agent that drafts escalate/inspect/defer decisions, a decision log, and a Mapbox map. Stack: Python core (pandas, 51 tests), FastAPI, SQLite, Next.js + TypeScript + Tailwind, Mapbox. Read `README.md`, `HANDOFF.md`, `CLAUDE.md`, `AGENTS.md`, and `CODING_GUIDELINES.md` before changing code. Keep the existing ranking working; it becomes a secondary tab.

### What we are building now
**Flowline Hazard Forecast.** For any pipeline area and its conditions (season, temperature, precipitation, substance, facility type, pipe attributes if present), Flowline:
1. Predicts the **mix of likely hazard types** (e.g. 41% equipment failure, 22% corrosion, 14% ground movement).
2. Shows the **most similar past incidents** (from incident narratives, via vector search) as evidence.
3. Maps each hazard type to the **crew and equipment** it needs (editable table).
4. In an emergency, **routes the matching crew** to the incident by the fastest road route.
5. Generates a short **readiness briefing** with an AI agent that only uses numbers from our tools.

One-liner: *"Their models tell you how strong the pipe is. Flowline tells you what kind of trouble to prepare for, and who to send."*

### Market position (do not contradict this in UI copy)
- TC Energy runs an in-house Quantitative Risk Assessment and the award-winning Psqr corrosion model (burst pressure from inline inspection). Third-party tools: Dynamic Risk, C-FER PIRAMID, MISTRAS, irth Solutions. All work on an operator's private inspection and asset data.
- Flowline is an **add-on, not a replacement**. It learns from the whole industry's public incident history (CER) and narratives, and outputs hazard-type mix + crew readiness. Never claim it certifies pipe safety or beats TC's risk models.
- Honesty line (keep in UI footer): *"Forecasts are based on historical public incident data. Flowline supports engineering judgment; it does not certify any pipe as safe."*

### Non-negotiable rules
- Work on branch `hazard-forecast`. Never push to `main`. Small, descriptive commits per step.
- Never commit `.env`, `.env.local`, API keys, or anything in `data/raw/`, `data/osm/`, `data/weather/`, model artifacts over 50 MB.
- **Ask me before** any system-level install, `sudo`, admin prompt, deleting files, or rewriting git history.
- **No invented numbers.** Every number in the UI or agent output must come from the database, the model, or the evaluation report.
- **Label sample data** (crew bases, crew/equipment table) clearly as "Sample — to be validated" in the UI.
- Do not break existing tests. Add tests for every new core module.
- If something fails or the data doesn't support a design choice, stop and tell me rather than working around it silently.

---

## Phase 1 — Environment setup

1. Detect OS (macOS / Windows / Linux) and report it.
2. Check versions: `git`, `node` (need 20+), `npm`, `python3` (need 3.11+), `docker`, `docker compose`. Report what's missing.
3. For anything missing, propose the install command for my OS (Homebrew on macOS, winget on Windows, apt on Linux) and **ask before running it**. Docker Desktop may need me to finish setup in its GUI; tell me exactly what to click, then verify with `docker run hello-world`.
4. Create and switch to branch `hazard-forecast` (if it doesn't exist).
5. Create folders:
   ```
   data/raw/  data/osm/  data/weather/  data/processed/
   docs/research/  design/current/  design/brand/
   models/  scripts/
   ```
6. Update `.gitignore` to exclude `data/raw/`, `data/osm/`, `data/weather/`, `data/processed/`, `models/*.bin`, `models/*.pkl`, `osrm/`, `.venv/`.
7. Create Python venv, install current `requirements.txt`, run existing tests (`pytest`) and `npm install && npm run build`. Report results.
8. Write `docs/research/MARKET_RESEARCH.md` from section 0 above (market position, competitor table, the gap Flowline fills).

**STOP & REPORT:** environment status, test results, anything I need to do by hand.

---

## Phase 2 — Data acquisition and profiling

1. Download into `data/raw/`:
   - `https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-comprehensive-data.csv`
   - `https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-data-dictionary.csv`
   (Handle encoding issues; the files may be Latin-1/cp1252.)
2. Download the Alberta OpenStreetMap extract from Geofabrik (`alberta-latest.osm.pbf`, under North America → Canada) into `data/osm/`. Warn me first: it's large.
3. Write `scripts/profile_cer.py` and produce `docs/DATA_PROFILE.md` with:
   - Row count, date range, rows in Alberta, rows per province.
   - Every column with type, % missing, and example values, cross-referenced with the data dictionary.
   - Which columns are **narrative text** (e.g. "what happened", "why it happened", summaries), their average length, and % filled.
   - Whether **pipe attributes** exist (material, diameter, wall thickness, install year, coating, pressure) and how complete they are.
   - The CER's cause / incident-type taxonomy with counts.
   - Coordinates completeness.
4. Propose a **hazard taxonomy of 8–10 groups** mapped from the CER's actual categories. Starting suggestion (adapt to the real data):
   - Corrosion (external / internal)
   - Cracking (incl. SCC)
   - Equipment & component failure (valves, fittings, seals, pumps, compressors)
   - Incorrect operation / procedures
   - Third-party & mechanical damage
   - Ground movement & geotechnical (slope, frost heave, subsidence)
   - Natural forces & weather (flood, lightning, extreme cold/heat)
   - Construction & material defects
   - Fire / ignition events (if not cause-based)
   - Other / unknown
   Produce the full mapping table (CER category → hazard group) with counts per group, nationally and for Alberta. Flag groups with too few examples to model.

**STOP & REPORT:** the data profile summary and the proposed taxonomy. Wait for my approval of the taxonomy.

---

## Phase 3 — Weather enrichment

1. Use Environment Canada historical climate data (climate.weather.gc.ca bulk data and station inventory). Confirm the current download method from official docs before coding.
2. `scripts/fetch_weather.py`:
   - Load the station inventory; for each incident, find the nearest station with daily data covering the incident date (prefer within 50 km; record the distance).
   - Download only the needed station-years. Cache to `data/weather/`, throttle requests (≥1 s apart), resume on failure.
3. For each incident compute, from daily data: mean/min/max temperature on the day and over the prior 7 and 30 days, total precipitation over the prior 7 and 30 days, snow on ground if available, and **freeze-thaw cycles in the prior 30 days** (days crossing 0 °C).
4. Record coverage: % of incidents with weather matched, median station distance. Mark weather features as missing (not zero) when unmatched.

---

## Phase 4 — Database: PostgreSQL + PostGIS + pgvector

1. Add `docker-compose.yml` with a PostgreSQL service that has **both PostGIS and pgvector** (use an image that ships both, or a small Dockerfile extending `postgis/postgis` with pgvector). Persistent volume, healthcheck, port 5432, credentials from `.env`.
2. Schema (adjust to profiled columns):
   - `incidents` (all cleaned CER fields, `geom geography(Point)`, `hazard_group`, `province`, `is_alberta`)
   - `incident_weather` (features from Phase 3)
   - `incident_embeddings` (`incident_id`, `embedding vector(384)`, `text_source`)
   - `corridors` (existing cleaned corridor logic, kept for the ranking tab)
   - `crew_types`, `hazard_crew_map` (hazard group → crew type → equipment list, `is_sample` flag)
   - `crew_bases` (name, location, crew types available, `is_sample = true`)
   - `decision_log` (migrate existing)
   - `pipelines` (load `public/pipelines_ab.geojson` into PostGIS)
3. `scripts/load_postgres.py`: idempotent loader. Migrate existing SQLite features (decision log, corridors) so the ranking tab still works. Keep the 51 existing tests passing, updating fixtures if needed.
4. Seed `hazard_crew_map` and `crew_bases` with clearly labeled sample data (e.g. Corrosion → integrity dig crew + NDE technician; excavator, UT gauge, coating kit. Ground movement → geotechnical crew; survey/GNSS, inclinometer. Equipment failure → mechanical/valve crew. Third-party damage → line locate + repair crew). Crew bases: 6–8 plausible Alberta towns near pipeline corridors (e.g. Edmonton, Edson, Grande Prairie, Hardisty, Fort McMurray, Red Deer, Calgary).

---

## Phase 5 — Narrative embeddings

1. Use `sentence-transformers` with `BAAI/bge-small-en-v1.5` (384 dims), running **locally**. No paid API for embeddings.
2. Build the text per incident from the narrative columns (concatenate "what happened" + "why it happened" + summary fields, cleaned). Record which fields were used.
3. Embed in batches, store in `incident_embeddings`, create an HNSW index (cosine).
4. Add `core/similar.py`: given an incident or a location+conditions context, return the top-k most similar past incidents with similarity score, date, location, hazard group, and a short narrative snippet. Similar-incident search for a *forecast* must only return incidents **before** the forecast's reference date.

---

## Phase 6 — Hazard forecast model and honest evaluation

### Prediction target
Given an **area + conditions** (no knowledge of the incident's own narrative or outcome), predict the probability of each hazard group *for an incident occurring there under those conditions*.

### Features (only information available before the incident)
- Location: lat/lon, province, region/corridor, distance to nearest pipeline, facility vs pipeline.
- Asset/context: substance, operator (grouped), pipe attributes if present.
- Time: month, season.
- Weather: Phase 3 features.
- **Area history:** counts and hazard mix of incidents within e.g. 25 km **before** the incident date; mean embedding of those prior incidents' narratives (reduced, e.g. PCA to 16 dims). Never include the target incident itself.

### Leakage rules (enforce in code and test them)
- The target incident's own narrative, cause fields, consequence fields, and anything recorded after the event are **never** features.
- Area-history and similarity features use strictly earlier incidents.

### Model
- LightGBM multiclass, class weights for imbalance. Keep it small and explainable.
- SHAP for per-prediction top drivers.

### Evaluation (`scripts/evaluate.py` → `docs/MODEL_REPORT.md`)
- **Time split:** train on incidents up to 2021-12-31, test on 2022 onward. Also report a rolling-origin check (e.g. test years 2020, 2021, 2022, 2023 separately).
- Baselines:
  1. National base rate (same mix for every incident).
  2. Alberta base rate.
  3. Area history only (hazard mix of prior incidents within 25 km).
- Metrics: multiclass log loss, Brier score, top-1 and top-3 accuracy, per-class recall, calibration plot (save PNG to `docs/`).
- Report results **for all of Canada and for Alberta only**.
- Include a "Where it fails" section: worst classes, sparse regions, and confusion matrix.
- Write the conclusion plainly. If the model does not beat the baselines, say so and propose why. Do not tune on the test set.

**STOP & REPORT:** the evaluation table, and whether weather and narrative features actually helped (ablation: with vs without each).

---

## Phase 7 — Backend API (FastAPI)

Add endpoints (Pydantic schemas, tests for each):
- `POST /forecast` — input: lat/lon or corridor, date, optional condition overrides (temperature, precipitation). Output: hazard probabilities, top drivers, evidence count, `low_evidence` flag.
- `GET /similar` — top-k similar past incidents for a context or incident id.
- `GET /crews` / `PUT /crews/map` — read/edit the hazard → crew → equipment table.
- `GET /readiness` — for an area and the next 7 days: forecast mix plus recommended crews. Upcoming weather from **Open-Meteo** (free, no key); fall back to manual sliders if offline.
- `POST /dispatch/route` — input: incident location and hazard group. Output: nearest crew bases that have the matching crew type, ranked by drive time, with route geometry.
- Keep all existing endpoints working.

---

## Phase 8 — Routing (OSRM, local)

1. Add an OSRM service to `docker-compose.yml`. Preprocess `data/osm/alberta-latest.osm.pbf` with the car profile using the MLD pipeline (`osrm-extract`, `osrm-partition`, `osrm-customize`) into `osrm/`. Make preprocessing a one-time script `scripts/build_osrm.sh` (and `.ps1` for Windows).
2. `core/routing.py`: drive time and route geometry between crew bases and an incident. Remote incidents may be off-road: snap to the nearest routable road and report the remaining straight-line distance as "last-mile, off-road".
3. Fallback: Mapbox Directions API if OSRM is unavailable and a token exists. If neither, show straight-line distance with a clear warning.

---

## Phase 9 — AI agent: switch to Gemini

1. Replace the Anthropic client in `core/agent/` with Google's current official Gemini Python SDK (`google-genai`). Check the current docs for the SDK usage and a current cost-efficient model name; read it from `GEMINI_MODEL` in `.env` (key in `GEMINI_API_KEY`).
2. Keep the existing design: the agent answers **only via tool calls** to our functions. Add tools: `get_forecast`, `get_similar_incidents`, `get_crews_for_hazard`, `get_readiness`, `get_dispatch_route`, plus existing ranking tools.
3. New capability: **Readiness briefing** — a short plain-English brief for an area and week ("Cold snap expected in Edson; ground movement share rises from X% to Y%; recommend geotechnical crew on standby at Edson base"). Every number must come from a tool result.
4. **Budget guard** (I have about $15 of credit): cap output tokens, cache identical requests for 10 minutes, log token usage per call to a file, and show a small usage counter in the dev console.
5. Optional offline fallback: if `OLLAMA_MODEL` is set and Gemini is unreachable, use local Ollama. The whole app (forecast, map, routing) must work with **no** AI key; only the briefing/chat is disabled.
6. Update agent tests (mock the client).

---

## Phase 10 — Frontend: command-center UI

Read the existing components first and reuse what makes sense. Screenshots of the current UI are in `design/current/` if present; brand ideas in `design/brand/` if present.

### Theme (our own identity; not TC Energy branding)
- Dark command-center look. Tailwind tokens:
  - `--bg` #0B1426 (deep navy), `--panel` #121E36, `--panel-2` #1A2A4A, `--border` #24365C
  - `--text` #E6EDF7, `--muted` #8CA0C3
  - `--accent` #F5A524 (amber, primary actions and highlights)
  - `--safe` #2DD4BF (teal), `--warn` #F59E0B, `--critical` #EF4444
- Mapbox dark basemap; pipelines in muted teal, incidents colored by hazard group, crew bases as distinct icons.
- Keep a light theme toggle only if cheap; dark is the default.

### Intro animation
- 2–3 seconds on first load: a glowing amber pulse travels along a line that bends into the Flowline mark, then the wordmark "FLOWLINE" fades in, then the dashboard fades up. Built with `framer-motion` (already installed) and SVG.
- Skippable by click or Escape. Shown once per browser session. Respect `prefers-reduced-motion` (show static logo for 0.5 s instead).
- Also produce the static logo as `public/logo.svg` and a favicon.

### Layout (single screen, no page hunting)
- **Top bar:** logo, area search, date / "next 7 days" toggle, condition overrides (temperature, precipitation sliders), tab switch: *Hazard Forecast* | *Risk Ranking* (existing) | *Decision Log*.
- **Center:** map (Alberta default, can zoom out to Canada). Click anywhere or on a corridor to forecast there.
- **Right panel — Forecast:** ranked hazard bars with percentages, top drivers (SHAP, in plain words), evidence count, "High risk, low evidence base" badge when applicable, comparison to Alberta average ("ground movement 2.1× Alberta average").
- **Right panel — Evidence:** 5 most similar past incidents: date, place, hazard, similarity, narrative snippet; click to fly to it on the map.
- **Bottom drawer — Readiness & Dispatch:** recommended crews and equipment for the top hazards (from the editable table, "Sample" label), an **Emergency dispatch** button: pick incident location → shows ranked crew bases by drive time with the route drawn on the map and ETA.
- **Crew table editor:** modal to edit hazard → crew → equipment mappings.
- **Briefing:** button that generates the readiness briefing via the agent; disabled with a tooltip if no key.
- Footer: honesty line and data sources (CER, Environment Canada, OpenStreetMap, Open-Meteo, Mapbox).

### Quality bar
- Responsive down to a 13" laptop. Loading skeletons, empty states, and error states everywhere. No layout shift on data load. Keyboard accessible. `npm run lint` and `npm run build` must pass.

---

## Phase 11 — One-command launcher and docs

1. `start.sh` (macOS/Linux) and `start.ps1` (Windows):
   - Check Docker is running (start it or tell me).
   - `docker compose up -d` (Postgres, OSRM), wait for healthchecks.
   - Run migrations/loader if the database is empty.
   - Start FastAPI and Next.js (production build for the demo), wait until both respond, open `http://localhost:3000`.
   - `stop.sh` / `stop.ps1` to shut everything down.
2. Update `README.md`: what Flowline Hazard Forecast is, setup from a fresh clone, data download steps, launcher usage, environment variables, and an **offline demo checklist** (what works without internet: forecast, map fallback, routing via OSRM; what needs internet: Mapbox tiles, Open-Meteo, Gemini).
3. Update `CLAUDE.md` / `AGENTS.md` with the new architecture.
4. Write `docs/DEMO_SCRIPT.md`: a 5-minute walkthrough. Suggested flow: intro animation → click Edson in winter conditions → forecast shifts toward cold-weather hazards → show similar past incidents → recommended crew → simulate an incident and dispatch → readiness briefing → model report slide with honest results.

---

## Phase 12 — Testing and final check

1. `pytest` all green (old and new). Add tests for: taxonomy mapping, weather feature calc, leakage guards (assert no future data in features), similarity date filter, forecast endpoint, routing fallback, crew map edits, agent tool-only numbers.
2. `npm run lint` and `npm run build` pass.
3. End-to-end smoke test from a fresh `start.sh`: forecast loads, similar incidents load, dispatch route draws, briefing works with key and degrades without it.
4. Run the full demo script once and fix anything rough.

**STOP & REPORT (final):** what works, model results summary, known limitations, and anything I should rehearse or fix by hand.

---

## Environment variables (`.env.example` to update)
```
# Backend
DATABASE_URL=postgresql://flowline:flowline@localhost:5432/flowline
GEMINI_API_KEY=
GEMINI_MODEL=
OLLAMA_MODEL=
OSRM_URL=http://localhost:5000
# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_MAPBOX_TOKEN=
```

## Data sources (cite in UI and README)
- Canada Energy Regulator, Pipeline Incident Data (Open Government Licence – Canada)
- Environment and Climate Change Canada, Historical Climate Data
- OpenStreetMap contributors (Geofabrik extract), routing via OSRM
- Open-Meteo (weather forecast)
- Mapbox (basemap)
- CER Pipeline Systems layer (route geometry, display only)
