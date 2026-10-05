# Backlog

## Washout watch (after Phase 10 is demoable · time-box 3 hours) — DONE: dropped

**Why:** post-2022 Alberta geotechnical incidents (mostly washout / erosion) followed
wetter months than other incidents, but raw station precipitation gave the model no
measurable gain (docs/MODEL_REPORT.md §4, §6).

**Try (only these):**
- 30-day rainfall **anomaly** vs each station's normal (same station, same calendar
  window, years before the incident only).
- Distance to the nearest **pipeline–waterway crossing**, using waterways from the
  Alberta OSM extract already in `data/osm/` and the CER pipeline systems layer.
- No slope / DEM work.

**Judge only on the rolling-origin check** (`scripts/evaluate.py` §3). Never look at
or tune on the 2022+ test set.

**Exit:** if it does not help on the rolling-origin check, drop it and keep the
descriptive finding (UI insight card, GET /insights/washout).

**Result (2026-10-05, ~70 min of the 3-hour box):** no candidate met the pre-registered
rule on 2016–2021 rolling origins (689 incidents pooled). Rainfall anomaly −0.005
[−0.023, +0.014], waterway crossings −0.005 [−0.023, +0.011], both −0.004 [−0.023, +0.015]
(Δ log loss, Canada). Alberta-only intervals also include zero. Features dropped; the
descriptive washout card and the river-crossing talking point remain. Details:
`docs/WASHOUT_WATCH.md`.
