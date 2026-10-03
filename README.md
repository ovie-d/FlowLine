# FlowLine — Tech Wolves · Case 10

IEEE YP Industry Hackathon · Energy & Infrastructure  
**Pipeline Incident Risk Agent** (David lane: `core/` + agent)

## Setup

```bash
pip install -r requirements.txt
```

Seed data: `data/cer_pipeline_incidents_alberta_2015.csv`  
(md5 `192d962494ed791c26225fccd20a5e28`)

## Run

```bash
# Required 5 Case steps
python -m core.deliverables

# Tests
pytest -q

# Agent (needs ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=...
python -m core.agent.loop "Explain why Sherwood Park ranks first at high=6"
```

## Honesty

We rank historic incident hotspots under an explicit risk policy.  
We do **not** certify any pipe as safe.

See `HANDOFF.md` and `CODING_GUIDELINES.md`.
