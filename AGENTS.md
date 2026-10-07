<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Flowline Hazard Forecast — architecture and rules

Read `README.md` first (product, setup, results); honest results in `docs/MODEL_REPORT.md`,
data facts in `docs/DATA_PROFILE.md`; the original v1 hackathon build is in `legacy/v1/`.

## Layout
- `core/` — all logic (pure functions where possible):
  - data: `cer.py` (load CER), `taxonomy.py` (cause codes → 8 forecast hazard groups +
    other/undetermined), `operators.py` (operator group, commodity from the CER systems
    layer), `sites.py`, `geo.py`, `weather.py`, `openmeteo.py`
  - model: `features.py` (leakage-safe features), `model.py` (LightGBM + prior
    correction + SHAP), `metrics.py`, `leakage.py`
  - product: `forecast.py`, `similar.py` (pgvector), `narratives.py` (pilot),
    `readiness.py`, `crews.py`, `routing.py`, `insights.py`, `mapdata.py`
  - agent: `agent/llm.py` (Gemini / Ollama), `agent/loop.py`, `agent/tools.py` +
    `agent/forecast_tools.py`, `agent/budget.py`, `agent/numbers.py`, `agent/prompts.py`
  - existing ranking product: `data.py`, `config.py`, `scoring.py`, `compare.py`, …
- `api/` — thin FastAPI routes (parse → core → return); `scripts/` — loaders,
  profiler, evaluation, OSRM build; `db/schema.sql`; `docker-compose.yml`.
- Frontend: `app/page.tsx` → `components/command/CommandCenter.tsx`; ranking tab in
  `components/ranking/RankingView.tsx`; API clients in `lib/forecastApi.ts`, `lib/api.ts`;
  hazard palette in `lib/hazards.ts` (validated; colours follow the hazard, never rank).

## Non-negotiable rules
- **No invented numbers.** Every number in the UI or agent output comes from the database,
  the model, the router, Open-Meteo or `models/hazard_forecast.eval.json`. The agent answers
  via tools only and `core/agent/numbers.py` flags unsupported numbers.
- **Leakage:** features use only information available before the reference date; area
  history is strictly earlier and a cause counts only once the incident was closed. Never use
  incident-record fields whose missingness tracks the cause (see DATA_PROFILE §9). Weather is
  **not** a model input (no measurable gain) — context only.
- **Never tune on the 2022+ test set.** Judge changes on the rolling-origin check.
- **Sample data** (crew types, crew map, crew bases) is labelled "Sample — to be validated".
- **Honesty line** stays in the footer; never claim a pipe is safe or that Flowline beats
  operators' integrity models.
- Don't change the deployed model without a discussion; re-run `scripts/evaluate.py` and
  update the report together.

## Commands
- Run: `./start.sh` / `./stop.sh` (Windows `start.ps1` / `stop.ps1`).
- Tests: `.venv/bin/pytest -q` (Postgres tests use a throwaway `flowline_test` DB; tests blank
  all AI keys and redirect the usage log). Frontend: `npm run lint && npm run build`.
- Data: `python -m scripts.load_postgres` (idempotent), `python -m scripts.evaluate`.
- Docker may need `sg docker -c "…"` in shells opened before joining the docker group.
