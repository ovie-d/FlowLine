# FlowLine

**Pipeline Incident Risk Agent** for Alberta CER corridor inspection priority.

Built by **Tech Wolves** for the IEEE YP Industry Hackathon (Case 10 · Energy & Infrastructure).

Count-only ranking sends crews to the *noisiest* corridor. FlowLine ranks corridors under an **explicit risk policy** (likelihood × consequence), explains every rank, and lets a planner triage and log decisions with an agent.

> We rank historic incident hotspots. We do **not** certify any pipe as safe.

---

## Features

- Risk-policy slider (count-only → balanced → severity-weighted)
- Ranked corridor list with drivers, moves vs baseline, and agent-draft labels
- Map of Alberta with CER pipelines (Mapbox Light+) and SVG offline fallback
- Corridor details and triage drafts (escalate / inspect / defer)
- Decision log — planner approves; the agent only drafts
- Case deliverables via `python -m core.deliverables`

---

## Tech stack

| Layer | Stack |
| --- | --- |
| Frontend | Next.js 16, React 19, Tailwind, Mapbox GL / react-map-gl |
| Backend | FastAPI, Pydantic, Uvicorn |
| Core | Python scoring, compare, assumptions, Claude agent tools |
| Data | CER Alberta incidents CSV → SQLite (`data/flowline.db`) |

---

## Prerequisites

- Node.js 20+
- Python 3.11+
- Anthropic API key (agent)
- Mapbox public token (optional; SVG map without it)

---

## Getting started

### 1. Clone and configure

```bash
git clone https://github.com/ovie-d/FlowLine.git
cd FlowLine

cp .env.example .env.local   # frontend
cp .env.example .env         # backend
```

Edit:

| File | Variable | Purpose |
| --- | --- | --- |
| `.env.local` | `NEXT_PUBLIC_API_URL` | FastAPI base (default `http://127.0.0.1:8000`) |
| `.env.local` | `NEXT_PUBLIC_MAPBOX_TOKEN` | Mapbox `pk.…` token |
| `.env.local` | `NEXT_PUBLIC_MAP_STYLE` | `light-plus` (default), `outdoors`, or `streets` |
| `.env` | `ANTHROPIC_API_KEY` | Agent LLM |
| `.env` | `AGENT_MODEL` | Optional model override |

Never commit `.env` / `.env.local`.

### 2. Backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Seed SQLite from the CER CSV (skip if data/flowline.db already populated)
python -m scripts.load_incidents

uvicorn api.main:app --reload --workers 1
```

- Health: http://127.0.0.1:8000/health  
- Docs: http://127.0.0.1:8000/docs  

Use **one worker** so agent sessions and decisions stay in memory.

### 3. Frontend

```bash
npm install
npm run dev
```

Open **http://localhost:3000** (restart after changing `.env.local`).

Map notes:

- With a Mapbox token → Light+ basemap + CER pipelines  
- Without → SVG “Offline map view”  
- Style switcher only at `?mapstyle=dev`

---

## Usage

1. Start the API, then the Next app.
2. Drag **severity weight** or pick a preset (Count-only / Balanced / Severity).
3. Select a corridor in the list or on the map.
4. Ask the agent to triage, explain, or escalate; **Approve** in the agent panel to log a decision.
5. Export rankings via **Export CSV** (hits `/ranking.csv`).

Case write-ups:

```bash
python -m core.deliverables
```

---

## Project structure

```text
FlowLine/
├── app/                 # Next.js app router (page, layout, providers)
├── components/          # Dashboard UI + map/
├── lib/                 # API client, types, formatters
├── api/                 # FastAPI routes + schemas
├── core/                # Scoring, compare, assumptions, agent
├── data/                # CER CSV + flowline.db
├── scripts/             # load_incidents, fetch_pipelines
├── public/              # Static assets (e.g. pipelines_ab.geojson)
├── tests/               # pytest
├── HANDOFF.md           # Product / scoring handoff
└── CODING_GUIDELINES.md
```

---

## API

Base URL: `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness |
| `GET` | `/ranking` | Ranked corridors (`high`, `top`) |
| `GET` | `/ranking.csv` | CSV export |
| `GET` | `/triage` | Draft escalate / inspect / defer |
| `GET` | `/corridor/{name}` | Corridor detail |
| `GET` | `/improvement` | Coverage vs count-only baseline |
| `POST` | `/compare` | Compare two policies |
| `GET` | `/assumptions` | Stated assumptions |
| `POST` | `/agent` | Chat / tool loop |
| `POST` | `/agent/reset` | Clear session |
| `GET` | `/decisions` | Logged decisions |

Interactive docs: `/docs`.

---

## Tests

```bash
source .venv/bin/activate
pytest -q
```

```bash
npm run build    # frontend typecheck + production build
```

---

## Disclaimer

FlowLine supports integrity planners under a **stated** risk policy. It does not replace engineering judgment, CER compliance systems, or per-asset integrity models. Thin-evidence corridors are flagged in the UI.

---

## Docs

- [HANDOFF.md](./HANDOFF.md) — product thesis, scoring, non-goals  
- [CODING_GUIDELINES.md](./CODING_GUIDELINES.md) — conventions  
- [data/README.md](./data/README.md) — dataset notes  

---

## License

Hackathon project · Tech Wolves · IEEE YP Industry Hackathon 2026.
