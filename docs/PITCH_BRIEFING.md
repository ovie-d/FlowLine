# FlowLine Pitch Briefing — Study Guide for David

IEEE YP Industry Hackathon · Case 10 · Tech Wolves  
Read this to prepare for the pitch and judges’ Q&A. Every number below was taken from running our code on the current seed unless marked **[verify]**.

Honesty line (memorize): **We rank historic incident hotspots under an explicit risk policy. We do not certify any pipe as safe.**

---

## 1. The problem in 60 seconds

Pipeline integrity teams have limited crews. Every Monday they choose which corridor to walk, inspect, or escalate.

If you only **count** incidents, you send crews to the **busiest** place — the noisiest corridor — not necessarily the **riskiest**.

A corridor with 33 mostly small fires and limit breaches can outrank one with fewer incidents but more serious releases. Busy isn’t risky.

**FlowLine** ranks Alberta corridors by how often things happened there and how serious those events were, under a risk policy the planner controls with one slider. We explain every rank, draft inspect / escalate / defer, and log the planner’s decision with the policy that was in effect.

---

## 2. Domain primer

### What the CER is
The **Canada Energy Regulator (CER)** oversees federally regulated pipelines in Canada. It publishes open **Pipeline Incident Data** (updated quarterly). Our seed is an Alberta slice of that file.

### What a pipeline corridor is (in this project)
A **corridor** is the stretch of pipe and facilities near one town — the nearest populated centre on the incident record (e.g. Edson, Sherwood Park). It is **not** a surveyed kilometre post or a licensed segment ID. Good enough to prioritize hotspots; not a GIS asset register.

### Pipeline integrity management
Operators run integrity programs (inspections, digs, repairs, monitoring) so lines stay fit for service. Our tool is **decision support** for “where does the next crew go under this policy?” — not a replacement for those systems, and not a CER compliance model.

### Risk = likelihood × consequence
Simple integrity idea:

- **Likelihood** — how often this corridor shows up in the history (incident frequency).
- **Consequence** — how bad those incidents were (severity of what happened).

We show both numbers separately, then combine them under explicit weights. That is our “matrix,” not a printed 5×5 colour grid.

### Sweet vs sour gas; crude
- **Sweet gas** — natural gas without significant hydrogen sulphide (H₂S). In our file often labelled `Sweet`.
- **Sour gas** — contains H₂S; higher consequence if released. Our seed has little/no explicit sour rows; the lab and our rules still treat sour as high when present.
- **Crude** — oil (e.g. `crude Sweet`, `crude Synthetic`). Treated as high consequence in our severity rules.

### CER incident types (plain words)
| Type in the data | Meaning |
|---|---|
| **Release of Substance** | Product left the pipe/system (gas, crude, diesel, etc.). |
| **Operation Beyond Design Limits** | Ran outside design limits (e.g. pressure) — a **limit breach**; often nothing released. |
| **Fire** | Fire at a facility or related site; often no release. |
| **Serious Injury (OPR)** | Serious injury as defined in the Onshore Pipeline Regulations. |
| **Adverse Environmental Effects** | Environmental harm recorded for the event. |
| **Explosion / Fatality** | Highest severity events in the set. |

### Operators in our seed (incident counts)
From our cleaned file (313 incidents):

| Company (short name in seed) | Incidents |
|---|---|
| NOVA Gas (NGTL / related) | 216 |
| Enbridge | 38 |
| Trans Mountain | 31 |
| Keystone | 8 |
| Others (Alliance, Express, Foothills, etc.) | remaining |

**Buyer angle:** NOVA Gas alone is 216 of 313 — this is largely an NGTL / TC Energy map, with Enbridge and Trans Mountain important on corridors like Sherwood Park.

---

## 3. Our data

**File:** `data/cer_pipeline_incidents_alberta_2015.csv`  
**md5:** `192d962494ed791c26225fccd20a5e28`  
**Scope:** 313 Alberta incidents, 2015-01-14 through 2026-08-24, originally 128 corridor name spellings.

### Columns
| Column | Meaning |
|---|---|
| `date` | When the incident occurred |
| `company` | Short operator name |
| `corridor` | Nearest town / place name |
| `substance` | What was involved (or Not Applicable) |
| `release_m3` | Volume released; empty if nothing released |
| `incident_type` | Fire, release, injury, etc. |
| `cause` | Cause category on the filing |
| `latitude` / `longitude` | Location |
| `consequence` | Organizer **lab** label (high / medium / low) — not an official CER risk score |

### The 141 dropped rows
Upstream of the seed, **141** Alberta filings with no usable date were excluded (mostly serious-injury filings without a timestamp). Our loader drops **0** additional no-date rows from this file. We still say the 141 out loud — it’s a limitation, not something we hide.

### Limits (say these early — they read as maturity)
- No pipe **length**, **age**, **material**, or **throughput** → we cannot do honest **per-km** risk. We don’t fake it.
- Historic incidents, **not** failure predictions.
- Small sample: **313** incidents; **60** corridors have only one incident; **87** have fewer than three (we flag thin evidence).

---

## 4. What we fixed vs the organizer’s starter

The starter (`agent_starter.py`) is a baseline to beat, not our foundation.

| Problem | What was wrong | What we do |
|---|---|---|
| Duplicate corridor names | Edson / Edson AB / Ab / Alberta, Hardisty AB, Sherwood Park AB, typos (Edmoton, Japser, FT MacKy, etc.) | Alias map → one canonical name |
| Junk names | `"17"`, `"8500"`, long Karr Receipt Point string | Snap to nearest corridor centroid within 40 km (or Unnamed lat/lon) |
| Mode-label scoring bug | Corridor score = count × **most common** consequence label (20 fires + 5 crude spills scored as all fires) | Weight **every** incident |
| One volume threshold | 100 m³ treated the same for gas and liquid | Separate: liquid high at 100 m³; gas high at 10,000 m³ (screening) |
| Injuries labelled low | Lab marked **34 of 35** serious injuries as low | Our `severity_v2` marks serious injuries **medium** |
| No tie-break | Unstable ranks at the cutoff | score ↓, n_high ↓, last_incident ↓, name ↑ |

### Before / after (from our cleaning report)
- Corridors: **128 → 112**
- Lab labels: high 50 / medium 40 / low 223  
- Our `severity_v2`: high **36** / medium **88** / low **189**  
- Edson merges: 8 rows from Edson AB/Ab/Alberta spellings into Edson (Edson ends at **33** incidents)

Junk snaps: Karr → Grande Prairie (39.0 km); 8500 → Branch Modular Home Park (4.43 km); 17 → Stony Plain (24.26 km).

These fixes are why the Edson ↔ Sherwood Park flip is real, not noise on dirty names.

---

## 5. How the score works (worked example: Sherwood Park)

Default weights: **high = 3**, **medium = 1.5**, **low = 1**.

For each corridor we:

1. Label every incident (`severity_v2` by default).
2. Sum the weights → **score**.
3. **Likelihood** ≈ number of incidents (16.0 for Sherwood Park).
4. **Consequence** = average weight (1.88 for Sherwood Park).

### Sherwood Park (default policy) — from `explain_corridor`
Word-for-word from code:

> Score 30.0 = sum of 16 incident weights (6 high × 3, 4 medium × 1.5, 6 low × 1); likelihood = 16.0 incidents; consequence = average weight 1.88.

Check: \(6×3 + 4×1.5 + 6×1 = 18 + 6 + 6 = 30\).

- Rank **#2**, confidence **ok**
- Operators: **Enbridge 10**, **Trans Mountain 6** (always name both)
- Last incident: 2023-07-25

### What the slider changes
The UI/API only changes how expensive **high** is (e.g. 1.5 → 3 → 6). Medium and low stay 1.5 and 1 unless someone changes config on purpose. Same CER file; different policy; different ranking.

At **high = 6**, Sherwood Park’s explanation becomes:

> Score 48.0 = sum of 16 incident weights (6 high × 6, 4 medium × 1.5, 6 low × 1); … consequence = average weight 3.0.

---

## 6. The flip: Edson vs Sherwood Park

| Policy | #1 | Why (short) |
|---|---|---|
| Low consequence (high ≈ 1.5) | **Edson** | Volume wins (33 incidents) |
| Default (high = 3) | **Edson** (score 41.5) | Still volume-led; only **2** high |
| Heavy (high = 6) | **Sherwood Park** (score 48.0) | Severity wins; **6** high of 16 |

**Edson at default:** n=33, n_high=2, score=41.5, L=33.0, C=1.26, mostly NOVA Gas.  
**Sherwood Park at default:** n=16, n_high=6, score=30.0, L=16.0, C=1.88.

**Demo line:** Same CER file. Drag the high weight. Different truck.

**Jenner (honesty + severity):** count-only **#26** → weighted **#12** (2 incidents, both high). Label: **High risk, low evidence base.** At heavy, Jenner is **#8**.

---

## 7. Proof it’s better (improvement round)

Judges want a visible **improvement round**: first result vs improved result vs a simple baseline.

We keep the **same weights** (3 / 1.5 / 1) and compare three rankings, then measure with a **label-independent yardstick**:

**Serious events** = incident types that are releases, explosions, fatalities, serious injuries, or adverse environmental effects — **not** our high/medium/low labels. Total serious in the file: **123**.

| Stage | Meaning | Serious in top 15 | Incidents covered (crew workload proxy) | Top 5 lead |
|---|---|---|---|---|
| **baseline** | Count-only | **62 / 123** | **169** | Edson, Grande Prairie, Edmonton, Sherwood Park, Hardisty |
| **lab** | Weighted with organizer labels | **66 / 123** | **163** | Edson, Sherwood Park, Hardisty, Edmonton, Grande Prairie |
| **ours** | Weighted with severity_v2 | **68 / 123** | **164** | Edson, Sherwood Park, Edmonton, Hardisty, Grande Prairie |
| **ours_heavy** | Ours + high=6 (slider) | **69 / 123** | **154** | Sherwood Park, Edson, Hardisty, Edmonton, Manning |

**Headline:** Ours captures **more** serious history (**68 vs 62**) while covering **fewer** total incidents (**164 vs 169**) than count-only. Same crew effort proxy, more of the dangerous history in the list.

Why label-independent? So we aren’t grading ourselves with our own high/medium/low stickers.

---

## 8. Triage (software drafts the Monday decision)

Rules (first match wins); threshold **3** high-consequence incidents to escalate (module constant, not a secret slider):

| Rule | When | Draft |
|---|---|---|
| R1 | n_high ≥ 3 and confidence ok | **escalate P1** |
| R2 | confidence low and n_high ≥ 1 | **inspect P3** (“High risk, low evidence base”) |
| R3 | n_high ≥ 1 or rank ≤ 5 | **inspect P2** |
| R4 | otherwise | **defer P3** (minor-only history; monitor) |

### Default (high=3)
Counts: **escalate 3 / inspect 8 / defer 4**

- Escalate: **Sherwood Park, Edmonton, Hardisty**
- Edson: **inspect P2** (busiest, not escalated — only 2 high)
- Jenner: **inspect P3** (thin evidence)
- Defer: Fort McKay, Fort McMurray, Bonanza, Sundre

### Heavy (high=6)
Counts: **escalate 3 / inspect 11 / defer 1**

- Sherwood Park takes **#1**; Edson drops to inspect #2
- Jenner rises to **#8**
- Deferrals shrink to **Fort McKay only**; Didsbury, Gordondale, Peers enter the top 15 with serious history

### Why the stable escalation list matters
At both high=3 and high=6, escalate stays **Sherwood Park, Edmonton, Hardisty**. Ranking moves with the slider; the **robust** escalate calls do not flip. That is a trust point for judges.

Drafts are **never** auto-logged. Planner approves; `log_decision` writes one corridor at a time with the **policy** attached.

---

## 9. The agent

### Architecture (as designed)
```
CER seed → core (clean, score, compare, triage, assumptions)
        → agent tools (read + log_decision)
        → FastAPI (Somrit) → frontend map/slider/chat (Jafar)
```
**In this repo today:** core + agent are shipped on `david`. FastAPI/UI are teammate hand-offs — **[verify]** live demo wiring before you claim a full stack on stage.

### Tools (6)
| Tool | When |
|---|---|
| `get_ranking` | Rank under a policy |
| `explain_corridor` | Why this corridor (L/C, operators, score_explanation) |
| `compare` | Overlap / movers between two policies |
| `get_assumptions` | Validation status + mentor evidence |
| `auto_triage` | Draft escalate / inspect / defer |
| `log_decision` | Planner explicitly records inspect/escalate/defer |

### Guardrails (say these)
- Numbers only from tools — no invented figures
- Never call a pipe/corridor safe or unsafe
- No inferred causes/vulnerabilities; leave conclusions to the engineer
- Short answers; use `score_explanation` word for word when explaining a score
- Name **every** operator with counts
- Human-in-the-loop: triage drafts ≠ logged decisions

Decision log fields include `policy` (e.g. high=6) and `source` (`planner` / `agent_triage`).

---

## 10. Industry validation (mentor, Oct 3)

Credit: **a pipeline integrity professional** (unless Immar confirms a fuller credit) **[verify credit wording with Immar]**.

| # | Mentor said | What we did |
|---|---|---|
| 1 | Prioritize serious releases; don’t just count; combine frequency, severity, volume, … | Validated `volume_vs_severity`; our weighted ranking + slider |
| 2 | Facility fires/limit breaches are context/indicators, not pipe failures | Validated `facility_events`; keep them in with **low** weight |
| 3 | 10,000 m³ gas OK as **screening** threshold; calibrate to operator classes later | Validated `gas_threshold` as screening, not gospel |
| 4 | Show sample size; label thin corridors | **High risk, low evidence base** (Jenner, Peers, …) |
| 5 | Don’t assume Edmonton = Sherwood Park without asset IDs | Validated `edmonton_sherwood`; keep separate |
| 6 | Ranked list with reasons, evidence, confidence; support judgment | Plain-English triage reasons + agent guardrails + closing line |

Still **unvalidated:** `injuries_medium` (we still treat serious injuries as medium); `triage_escalate_min_high` (not asked; escalate set stable at 3 and 6 on this seed).

---

## 11. Judging rubric — where we score

| Criterion | Weight | Where we hit it |
|---|---|---|
| **Autonomous reasoning + data-driven decisions** | **30%** | Clean → score → improvement round (62→68 serious) → triage drafts → planner log with policy |
| **Real problem / industry relevance** | 20% | Integrity crew prioritization; NGTL-heavy map; mentor validation |
| **Execution / working demo** | 20% | Deliverables, flip, triage, agent tools, tests (27 passing at last check) **[verify count before stage]** |
| **Commercialization** | 15% | One buyer, Monday decision, pilot path, explicit non-goals |
| **Presentation** | 15% | Pain → Jenner → flip → decision → honesty; one improvement number |

Don’t open with architecture. Lead with pain and the flip.

---

## 12. Commercialization

**Buyer:** integrity planner at **NGTL / TC Energy** or **Enbridge** choosing the next crew.

**Monday decision:** inspect / escalate / defer — not “explore a dashboard.”

**Pilot [verify commercial detail with Immar]:** one operator integrity team, Alberta CER slice, weekly ranking under their consequence weight, log decisions for 4–8 weeks, compare to their current call sheet.

**Scale path:** quarterly CER refresh; more provinces; later join operator asset data (age, material, length) for per-km risk — only when that data exists.

**Positioning:** decision support under an **explicit policy**. Not a replacement for integrity management systems. Not a prediction engine.

---

## 13. Limitations and honest answers

- Small sample (313); many thin corridors — we flag them.
- No per-km normalization without length/throughput.
- Historic hotspots, not predictions.
- Gas 10,000 m³ and triage threshold 3 are **screening** assumptions.
- One mentor conversation so far; some assumptions still unvalidated.
- 141 undated filings never enter the score.
- Lab vs our labels differ on purpose (injuries, etc.) — we show both in the improvement round.

---

## 14. Numbers cheat sheet

| Number | Meaning |
|---|---|
| 313 | Incidents scored |
| 141 | Upstream dropped (no date) |
| 128 → 112 | Corridors before → after cleaning |
| 216 / 313 | NOVA Gas share |
| high 3 / med 1.5 / low 1 | Default weights |
| Edson 33 / 2 high / score 41.5 | Default #1 |
| Sherwood 16 / 6 high / score 30.0 | Default #2 |
| Sherwood score 48.0 at high=6 | Heavy #1 |
| Jenner #26 → #12 (#8 at heavy) | Thin but serious |
| 62 → 66 → 68 / 123 | Serious captured: baseline → lab → ours |
| 169 → 164 | Incidents covered: baseline → ours |
| 69 / 154 | ours_heavy serious / covered |
| escalate 3 / inspect 8 / defer 4 | Default triage |
| escalate 3 / inspect 11 / defer 1 | Heavy triage |
| Enbridge 10, Trans Mountain 6 | Sherwood Park operators |
| 34 of 35 | Serious injuries labelled low in lab |
| 60 | Corridors with only 1 incident |

---

## 15. Thirty likely judge questions (short answers)

1. **What problem are you solving?** Limited integrity crews; count-only sends them to busy corridors, not necessarily high-consequence ones.  
2. **Who is the user?** Integrity planner at NGTL/TC Energy or Enbridge — Monday inspect/escalate/defer.  
3. **Where does the data come from?** CER Pipeline Incident Data; Alberta seed 2015–Aug 2026, 313 rows.  
4. **Why Alberta only?** Case seed; NOVA/NGTL-heavy; expand later.  
5. **Is this predictive ML?** No. Transparent weighted historic ranking + rules.  
6. **Why not ML?** Tiny labelled set, need explainability and policy control; ML later with more features.  
7. **What is likelihood / consequence?** Frequency vs average severity weight under the policy.  
8. **What does the slider do?** Changes the high-consequence weight only.  
9. **Show me the flip.** Edson #1 at high=3; Sherwood Park #1 at high=6.  
10. **How do you know you’re better than count-only?** Improvement round: 62→68 serious events in top 15, fewer incidents covered.  
11. **What’s your yardstick?** Serious CER incident types — label-independent.  
12. **Did you change the labels to win?** We document lab vs v2; yardstick doesn’t use our labels.  
13. **What about dirty town names?** Aliases + junk snaps; 128→112.  
14. **Starter scoring bug?** Mode label × count; we weight every incident.  
15. **Injuries?** Lab: 34/35 low; we treat serious injury as medium.  
16. **Gas vs liquid?** Separate thresholds; 10,000 m³ gas is a screening assumption (mentor-validated as such).  
17. **Is 10,000 m³ regulatory?** No — screening; calibrate to operator classifications.  
18. **What is triage?** Rule drafts escalate/inspect/defer; planner approves.  
19. **Why escalate those three?** ≥3 high and confidence ok: Sherwood Park, Edmonton, Hardisty.  
20. **Why not escalate Edson?** Only 2 high despite 33 incidents.  
21. **What is Jenner?** 2 high incidents; #26→#12; High risk, low evidence base.  
22. **Does the agent auto-approve?** No. Human-in-the-loop logging only.  
23. **Can it invent numbers?** Guardrailed to tool results only.  
24. **Do you say pipes are unsafe?** Never. Historic hotspots under a policy.  
25. **Edmonton vs Sherwood Park same site?** Mentor: don’t assume without asset IDs; we keep separate.  
26. **Facility fires — include?** Yes, as context at low weight; mentor-aligned.  
27. **Per-km risk?** Can’t without length; we don’t fake it.  
28. **How do you commercialize?** Pilot with one integrity team; quarterly CER refresh; later asset join.  
29. **Competition?** Spreadsheets and count dashboards; we add explicit policy, explanation, decision log.  
30. **Biggest limitation?** Small sample + no asset attributes; thresholds are screening assumptions.

---

## 16. Glossary

| Term | Plain meaning |
|---|---|
| Corridor | Town-level hotspot bucket for incidents |
| Likelihood | How often incidents occurred there |
| Consequence | How severe those incidents were (average weight) |
| Risk policy | The weights you choose (especially high) |
| Lab label | Organizer’s high/medium/low on the CSV |
| severity_v2 | Our corrected per-incident severity |
| Count-only | Rank by number of incidents alone |
| Improvement round | Baseline → lab → ours measured on serious events |
| Triage | Draft escalate / inspect / defer |
| High risk, low evidence base | Thin sample, serious signal — don’t over-claim |
| CER | Canada Energy Regulator |
| NGTL | NOVA Gas Transmission Ltd. system (TC Energy) |

---

## 17. What to research further (for Q&A depth)

| Topic | Why it matters | Start here |
|---|---|---|
| CER incident data + dictionary | Defend columns, dates, substance, types | [CER open incident CSV](https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-comprehensive-data.csv), [data dictionary](https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-data-dictionary.csv), [Open Gov portal](https://open.canada.ca/data/en/dataset/7dffedc4-23fa-440c-a36d-adf5a6cc09f1) |
| CER / CSA Z662 integrity basics | Speak the buyer’s language (IMS, digs, assessments) | CER safety & integrity pages; CSA Z662 overview materials **[verify latest public summaries]** |
| Risk matrices in integrity management | Explain likelihood × consequence without sounding academic | Standard IMS / risk-matrix primers; tie back to our slider as an explicit policy, not a hidden score |
| Operator incident classifications | Mentor said calibrate gas threshold to these | Ask Immar / mentors for public examples **[verify]** |
| NGTL / Enbridge integrity programs (public) | Commercialization Q&A | Company integrity reports / CER filings **[verify]** |

---

## Closing lines (pick one to end)

1. We rank historic hotspots under your consequence weight. We don’t certify pipes.  
2. Change the policy and the software re-decides — watch corridors move between escalate, inspect, and defer.  
3. The tool supports the integrity engineer’s decision. It doesn’t replace engineering judgment.

---

*Generated for Tech Wolves Case 10. Re-run `python -m core.deliverables`, `draft_triage`, `explain_corridor`, `improvement_round`, and `get_assumptions` before the final pitch if the seed or weights change.*
