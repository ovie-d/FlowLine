# Demo script — Flowline Hazard Forecast (5 minutes)

> **One-liner:** *Their models tell you how strong the pipe is. Flowline tells you what
> kind of trouble to prepare for, and who to send.*

Numbers below are from the 2026-10-05 data load and evaluation. They change if the data
is reloaded — rehearse with the live screen, and re-read `docs/MODEL_REPORT.md` after any
re-run. Backup answers: `docs/QA_PREP.md`.

**Before you start:** `./start.sh` (or `start.ps1`). Open a **fresh private window** so the
intro plays. Check: API up, map loaded, `GEMINI_API_KEY` set (for the briefing), Mapbox
token set (for the basemap — otherwise the offline Alberta map is used and everything
still works). On a 13" screen the readiness drawer starts collapsed; open it when you
reach crews.

---

## 0:00 — Intro (15 s)
The amber pulse runs along the line and becomes the Flowline mark.
> "Flowline is an add-on for integrity and operations teams. It learns from the whole
> industry's public incident record — every CER-regulated operator — and answers a
> readiness question, not a pipe-strength question."

## 0:15 — The map (20 s)
Point at the coloured dots and teal lines.
> "Two thousand CER incidents since 2008, coloured by hazard type, on the CER pipeline
> systems. White squares are crew bases — **sample data**, clearly labelled, to be
> replaced by an operator's real crews."

## 0:35 — Forecast Edson, next 7 days (60 s)
Search **Edson** (Next 7 days).
- Bars: **ground movement & washout 36%** — **3.1× the Alberta average** — then incorrect
  operation 19%, equipment failure 14%.
- Click the top bar: drivers in plain words (time of year, nearby history).
- Evidence line: **24 earlier incidents at 16 sites within 25 km**.
- Weather card: Open-Meteo outlook — "context, **not a model input**".
> "This is a mix, not a single prediction. Every number on this panel comes from the
> model or the database."

## 1:35 — Season matters (35 s)
Switch to **Pick date**:
- **January 2027** → equipment failure leads (**40%**).
- **July 2027** → ground movement shows **">50%, lower certainty"**.
> "The mix shifts with the time of year — learned from history. Above 50% we deliberately
> say *lower certainty*: on held-out data the model was overconfident there."

Switch back to **Next 7 days**.

## 2:10 — Similar past incidents (25 s)
Click one of the five similar incidents → the map flies to it.
> "Evidence, not a black box: nearby incidents from before today, with their recorded
> causes. Public CER data only has cause codes — the narrative search is built and ready
> for an operator's incident narratives in a pilot."

## 2:35 — Who to have ready (25 s)
Open the **Readiness & dispatch** drawer.
> "For the top hazards: geotechnical and erosion-control crews from the Edson base,
> about 10 minutes away. Sample crew table — planners edit it here." (Optionally open
> **Edit crew table**.)

## 3:00 — Emergency dispatch (35 s)
Click **Emergency dispatch**, then a point west of Edson near Hinton.
> "Ranked by real drive time on local OpenStreetMap routing — Edson first, about an hour,
> route drawn. If the site is off-road we show the last mile separately; with no router
> we fall back to straight-line distance and say so."

## 3:35 — Readiness briefing (30 s)
Click **Generate briefing**.
> "The AI writes the briefing only from tool results — and we check every number against
> them. That green tick means every figure traces back to the data." (If the key isn't
> set, the button explains why; everything else works without AI.)

## 4:05 — An honest pattern (15 s)
Point at the washout card.
> "Since 2022, washouts and ground movement rose from 8.5% to 22.0% of Alberta incidents
> — 2.6× — and followed wetter months. That's an observed pattern, not a forecast; the
> model can't learn it yet from the earlier years."

## 4:20 — How good is it? (35 s)
Click **About this model**.
> "Tested on 2022-onward incidents it never saw. **Across Canada the model clearly beats
> simple history.** In Alberta the gain is real but narrow. **On NGTL alone, public data
> isn't enough yet — which is why a pilot with operator data matters.**"

## 4:55 — Close (5 s)
> "Forecasts are based on historical public incident data. Flowline supports engineering
> judgment; it does not certify any pipe as safe."

---

## Q&A notes

**"Is it just learning each operator's reporting habits?"**
Mostly no. Removing the operator made no measurable difference across Canada (log loss
−0.010, 95% CI −0.027 to +0.009). A model with no operator, province or commodity —
just place, time of year and nearby history — still clearly beats simple history
(−0.139). The data can't fully separate asset type from reporting practice, so we read
operator effects as "this operator's history looks like this", not as causes.

**NGTL detail:** 122 held-out NGTL incidents; model vs best baseline −0.037 (CI −0.107 to
+0.028) = not distinguishable. All other operators: −0.183 (CI −0.241 to −0.125).

More answers: `docs/QA_PREP.md`.

## If something breaks
- **Map shows "Offline map view"** — no Mapbox token or no internet; the demo still works.
- **Weather card says unavailable** — no internet; say "weather is context only".
- **Briefing disabled** — no `GEMINI_API_KEY`; show the tooltip, move on.
- **Dispatch shows "straight-line distance only"** — OSRM isn't running
  (`docker compose up -d osrm`).
- **Nothing loads** — `./stop.sh && ./start.sh`; logs in `logs/`.
