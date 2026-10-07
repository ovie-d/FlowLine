# Changelog

All notable changes to Flowline. Versions follow [semantic versioning](https://semver.org/).

## [2.0.0] — 2026-10-06

Flowline becomes **Flowline Hazard Forecast**: from "which corridor to inspect" to "what
kind of trouble to prepare for, and who to send". The v1 Risk Ranking and Decision Log
remain as tabs.

### Added

**Forecasting**

- **Hazard forecast:** a LightGBM model gives the probability of 8 hazard groups for any
  point or area and date.
  - Trained on national CER incident history with leakage-safe features: area history
    uses only earlier, closed incidents.
  - SHAP drivers per hazard, comparison with the Alberta average, a low-evidence flag, and
    "lower certainty" labels above 50%.
- **Honest evaluation** (`scripts/evaluate.py` → `docs/MODEL_REPORT.md`): time split (train
  ≤ 2021, test 2022+), rolling-origin check, baselines, ablations, an operator-dependence
  check, per-class failures and calibration.
- **Similar past incidents** as evidence: pgvector similarity on place, season, weather and
  commodity, strictly before the forecast date.

**Readiness and dispatch**

- **Readiness:** crews and equipment per hazard (editable table, labelled sample data), the
  nearest crew base by drive time, and the 7-day weather outlook from Open-Meteo (context
  only).
- **Emergency Dispatch page:** a pin by click or search, the hazard prefilled from the
  forecast, and crew bases ranked by OSRM drive time with every route drawn.
  - The off-road last mile is shown separately.
  - A response timeline is clearly labelled as a simulation.
  - It includes an equipment checklist and a printable one-page summary.
- **AI readiness briefing** (Gemini, optional): written from tool results only. Every number
  is checked against them, with a budget guard and usage log.

**Maps and interface**

- **Interactive map:**
  - Basemaps: dark, light, streets and satellite; 3D terrain; a globe view.
  - Layers: incident clusters, heatmap, pipelines, crew bases, pipeline–waterway crossings.
  - Incident detail popups with plain-English CER cause codes, and a year slider with play.
- **Works without keys:** with no Mapbox token the maps run on MapLibre GL with open
  basemaps (OpenFreeMap, Esri imagery). Without a Gemini key the briefing is off with a
  clear message.
- **Light theme** (dark stays the default), WCAG AA contrast, animated forecast bars, and
  tooltips for every number and badge.

**Install and run**

- **One-line install** for Linux/macOS (`install.sh`) and Windows (`install.ps1`), plus
  one-command `start` / `stop` scripts.
  - The launchers rebuild the web app only when needed.
  - Road routing (OSM download, OSRM build) and the river-crossings layer are prepared in
    the background, so the first run opens quickly.
- **Desktop app** (Electron, Linux AppImage): starts the services, waits for the health
  checks, and stops them on close.
  - WebGL is forced on, with a software fallback.
  - `install-linux.sh` adds a menu entry and a trusted desktop icon.
  - Windows `.exe` and macOS `.dmg` are built by GitHub Actions; unsigned and untested.
- **Docker services:** PostgreSQL 18 + PostGIS + pgvector, and OSRM.

### Changed

- The original v1 planning docs and starter script moved to `legacy/v1/`, credited to the
  Tech Wolves team.

### Known limitations

- Across Canada the forecast clearly beats simple baselines. In Alberta the gain is narrow,
  and on NGTL alone it is not yet distinguishable from simple history. See
  `docs/MODEL_REPORT.md`.
- Rare hazards (third-party damage, fire / ignition, construction & material) are forecast
  poorly, and probabilities above 50% were overconfident.
- Crew bases, crew types and equipment are sample data until an operator validates them.
- The Windows scripts and the Windows/macOS desktop builds haven't been run on those
  systems yet.

## [1.0.0] — 2026-10-04

The original hackathon build by the **Tech Wolves** team (IEEE YP Industry Hackathon,
October 2–4, 2026, Case 10). Plan and starter code: [`legacy/v1/`](legacy/v1/).

- **Corridor risk ranking** for Alberta pipeline corridors under an explicit
  likelihood × consequence policy, with one slider the planner controls, compared against
  count-only ranking.
- **Explainable ranks:** score breakdowns and plain-English reasons, including the operators
  in each corridor.
- **Agent:** triage drafts (inspect / escalate / defer) and corridor explanations from tool
  results; drafts only, the planner approves.
- **Decision Log:** approved decisions stored (JSON, SQLite or Postgres).
- **API and dashboard:** a FastAPI pass-through over the core, and a Next.js dashboard with a
  Mapbox basemap of CER pipelines and an SVG fallback.

[2.0.0]: https://github.com/ovie-d/FlowLine/releases/tag/v2.0.0
[1.0.0]: https://github.com/ovie-d/FlowLine/tree/857237d
