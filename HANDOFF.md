# Tech Wolves — Case 10 Handoff (FINAL): Pipeline Incident Risk Agent

IEEE YP Industry Hackathon · Oct 2–4, 2026 · Energy & Infrastructure stream
Scope owner: David (AI / Data / Core). Read with `CODING_GUIDELINES.md`.

---

## 1. The big idea

Pipeline integrity teams have limited crews. Count-only prioritization sends them to the
**noisiest** corridor, not the **riskiest**.

We rank Alberta pipeline corridors by **risk = likelihood × consequence**, expose that risk
policy as one slider the planner controls, explain every rank, and let the planner log the
decision. The ranking is correct **under a stated policy, and we show the policy.**

> **One-liner:** Count-only sends crews to the noisiest corridor. We send them under an explicit
> risk policy, and show exactly why.

**The flip (headline finding):** With a low consequence weight, Edson is #1 (33 incidents,
mostly fires and limit breaches; only 2 high-consequence). Drag the high-consequence weight to 6
and Sherwood Park takes #1 (16 incidents, 6 high-consequence). Same data. Different risk policy.
Different crew destination.

**Win thesis (do not dilute):**
1. **Pain:** count-only = noisy, not risky.
2. **Proof:** Edson → Sherwood Park flip under one slider drag.
3. **Trust:** every assumption visible, validated with industry people where possible, no "safe pipe" claims.

**Honesty line (always):** We rank historic incident hotspots. We do not certify any pipe as safe.

### Non-goals (say these early, they read as maturity)
- No pipe length, age, material, or throughput in the data, so no per-km risk. We don't fake it;
  we make the volume-vs-severity trade-off explicit instead.
- Not a CER compliance model, not a replacement for integrity management systems.
  Decision support for crew prioritization under an explicit policy.
- Small sample: 313 incidents, ~75 corridors with a single incident. Thin corridors are flagged.

---

## 2. Buyer

**One buyer:** pipeline integrity planner at NGTL / TC Energy or Enbridge, choosing which
corridor gets the next crew.

**Why:** NOVA Gas / NGTL = 216 of 313 incidents. This is their map.
**Monday decision:** inspect / escalate / defer, not "explore a dashboard."

---

## 3. Why our ranking beats the starter (credibility layer)

1. **Duplicate corridors:** same town under several spellings (Edson / Edson AB / Edson Ab /
   Edson Alberta; Hardisty AB; Sherwood Park AB; Manning AB; Grande Cache AB; Edmoton; FT MacKy;
   Fort Mcmurray; Town of Japser; Zama vs Zama City). 128 corridors → ~111 after cleaning.
2. **Junk corridor names:** "17", "8500", "Karr Receipt Point is approximately 95 km SE of Grande Prairie".
3. **Scoring bug:** starter multiplies each corridor's count by its *most common* label. A corridor
   with 20 fires and 5 crude spills is scored as all fires. Fix: weight every incident.
4. **One volume threshold for gas and liquid:** 100 m³ of gas ≠ 100 m³ of crude.
5. **Serious injuries labelled "low"** (34 of 35).
6. **No tie-break** at rank 15.
7. 141 rows dropped upstream for missing dates (mostly serious-injury filings). Stated as a limitation.

These fixes are what make the flip real instead of noise on dirty names.

---

## 4. Product spec (win path)

### Layout
```
core/
  data.py         # load + clean + per-incident features
  config.py       # RiskConfig + presets
  scoring.py      # score(config) -> ranked corridors with components
  compare.py      # overlap + movers between two configs
  assumptions.py  # 4–5 live assumptions with validation status + evidence
  deliverables.py # prints the 5 required steps
  agent/
    tools.py
    prompts.py
    loop.py
data/cer_pipeline_incidents_alberta_2015.csv
tests/test_core.py
```

### data.py — clean once, cache
- Drop rows with no date; report count.
- Keep `corridor_raw`; `corridor` = alias-mapped name.
- Junk names → snap to nearest corridor centroid by lat/lon within 40 km, else
  `"Unnamed (lat,lon)"`. Log every snap.
- Per-incident features:
  - `substance_class`: gas | liquid | none
  - `event_class`: release | facility_event (fire / limit breach, nothing released) | harm (injury / fatality / explosion)
  - `severity_lab`: original label (kept for comparison)
  - `severity_v2`: our label
    - high: explosion, fatality, crude or sour substance, liquid ≥ 100 m³, gas ≥ `gas_high_m3`
    - medium: other releases, adverse environmental effects, serious injury
    - low: fires / limit breaches with no release
  - `age_years`: relative to latest date in file (kept for later; not in demo)
- Returns `(df, cleaning_report)`: drops, merges, snaps, relabel counts.

### config.py
```python
@dataclass(frozen=True)
class RiskConfig:
    weights: dict = {"high": 3.0, "medium": 1.5, "low": 1.0}  # high = THE slider
    label: str = "v2"                  # "v2" | "lab"
    half_life_years: float | None = None   # off for demo
    include_facility_events: bool = True   # may change after mentor input
    min_incidents_confident: int = 3
    gas_high_m3: float = 10_000        # UNVALIDATED until mentor/source
    liquid_high_m3: float = 100
    count_only: bool = False           # baseline
```
Scoring is `sum` only: each incident contributes weight × (optional) age decay.
Presets: `BASELINE_COUNT`, `LOW_CONSEQUENCE` (high ≈ 1.5), `CONSEQUENCE_HEAVY` (high = 6).
API and UI only edit this object. No formula hardcoded anywhere else.

### scoring.py — `score(config, top=15) -> list[dict]`
Must-demo fields per row:
```json
{
  "rank": 1, "corridor": "Edson", "score": 41.5,
  "likelihood": 33.0, "consequence": 1.26,
  "n": 33, "n_high": 2,
  "confidence": "ok",
  "drivers": [{"date": "...", "type": "...", "substance": "...", "weight": 3.0}]
}
```
Also returned (API sugar): `n_medium`, `n_low`, `operator`, `lat`, `lon`, `last_incident`.
- `likelihood` = weighted incident count; `consequence` = average severity weight. Always separate.
- Tie-break: score ↓, n_high ↓, last_incident ↓, name ↑.
- `confidence = "low"` when `n < min_incidents_confident`.
- `drivers` = top 3 incidents by contribution.

### compare.py — `compare(cfg_a, cfg_b, top=15)`
Returns `overlap`, `entered`, `dropped`, `movers[{corridor, from, to, delta, reason}]`;
`reason` names the component that moved it (likelihood vs consequence).

### assumptions.py — only the ones that matter
```python
{"id": "gas_threshold", "statement": "Gas release >= 10,000 m3 is high consequence",
 "status": "unvalidated",   # validated | sourced | unvalidated
 "evidence": "", "affects": ["gas_high_m3"]}
```
Seed (max 5): crew priority volume vs severity · facility fires/limit breaches count for pipe walks ·
gas threshold · injuries ≥ medium · Edmonton & Sherwood Park same facility?
Immar fills `evidence` after mentor conversations today.

### deliverables.py — the 5 required steps
1. Rows loaded / dropped (no date).
2. Corridors before/after cleaning; incident counts.
3. Top 15 by count × consequence.
4. Top 15 vs count-only overlap; raise high weight, overlap again.
5. Three corridors that rose or fell, with reasons.

---

## 5. Agent (thin, with one action)

**Job:** explain likelihood vs consequence, cite assumptions, and record the planner's decision.
Never invents numbers.

| Tool | Does |
|---|---|
| `get_ranking(config overrides)` | Ranked corridors under a given policy |
| `explain_corridor(name)` | Likelihood vs consequence, incident types, causes, drivers |
| `compare(a, b)` | Overlap + movers with reasons |
| `get_assumptions()` | Live assumptions with validation status + evidence |
| `log_decision(corridor, action, priority, reason)` | Records inspect / escalate / defer → JSON log |

`log_decision` is what makes this an agent, not a chatbot: it turns the ranking into the
Monday decision. Fires only when the planner explicitly asks.

System prompt rules:
- Never say a pipe or corridor is safe/unsafe; we rank historic hotspots.
- Numbers only from tool results.
- Explain ranks via likelihood vs consequence and drivers.
- Flag when an answer depends on an unvalidated assumption; cite mentor evidence when it exists.

**Banned phrases (agent, UI copy, pitch):** "safer corridors," "high-risk pipes," "predict failures."
**Use:** "historic hotspot ranking under your consequence weight."

---

## 6. Team interfaces

- **David — AI/Data/Core:** everything in `core/` + agent.
- **Somrit — Backend:** FastAPI wrapper. `GET /ranking` (config as query params),
  `GET /corridor/{name}`, `POST /compare`, `GET /assumptions`, `POST /agent`
  (history server-side), `GET /decisions`, `GET /health`.
- **Jafar — Frontend:** map + **one** high-weight slider + count-only toggle + corridor panel
  (likelihood vs consequence, drivers, confidence badge) + agent chat with tool-call chips +
  decisions list. No mode selector. No extra sliders.
- **Immar — Integration/Pitch/Research:** mentor conversations today, assumption evidence,
  demo script, pitch.

---

## 7. Demo spine (lock this order)

**Beat 1 — Pain (no slider yet).** Count-only top 15, Edson on top.
"Busy is not the same as risky. Limited crews; the wrong map wastes the week."
Then the small proof before any drag: **Jenner** is #26 under count-only and #12 under weighted
ranking, because both of its incidents are serious releases. The count map already mis-ranks real severity.
Jenner shows a low-confidence badge (2 incidents). Say it out loud: "Thin data, so we flag it,
but count-only buried it." That's a severity point and an honesty point in one.

**Beat 2 — Flip.** Slider starts low (high ≈ 1.5): Edson #1. Drag live to 6: Sherwood Park #1.
Corridor panel side by side: n vs n_high, likelihood vs consequence.
"Same CER file. Different risk policy. Different truck."

**Beat 3 — Decision, then trust (decision log is a beat, not the curtain).**
1. Agent explains Sherwood Park's drivers (~15 s).
2. Planner: "Escalate Sherwood Park, P1." Decision appears in the log (~5 s, one sentence:
   "The Monday decision is captured."). Don't linger on the log UI.
3. One line of mentor evidence: "We asked integrity engineers where they'd send the crew; here's what they said and what we changed."
4. Flash one still-unvalidated assumption (e.g. gas threshold).
5. **Last words in the room:** "We rank historic hotspots. We don't certify pipes. Every assumption is labelled."

Rehearse this order with a timer. If short on time, cut step 4 before cutting step 5.

**Hard rules:** don't open with architecture or tool lists. Don't show stretch work.
If time remains: one credibility slide (§3), then stop.

---

## 8. Mentor validation (today)

Top 3 questions (Immar):
1. "One crew, two corridors: 30 small fires/limit breaches vs 6 serious releases. Where do you send them, and why?"
2. "Do facility fires and limit breaches matter for deciding which pipe to walk?"
3. "What gas release volume would you call serious?"

Rules:
- Log role (not name unless OK), answer, and what we changed → `assumptions.py` evidence.
- **If feedback changes the ranking, follow the evidence.** "Industry feedback changed our model"
  is a stronger story than protecting the flip. Update the pitch numbers accordingly.

---

## 9. Build order

1. `data.py` + `config.py` → ~111 corridors; cleaning report printable.
2. `scoring.py` → Edson #1 at low weight; Sherwood Park #1 at high = 6. Pytest it.
3. `compare.py` + `deliverables.py` → required 5 steps done; Somrit wraps API.
4. Agent: 4 read tools + `log_decision`. Stop. Polish demo.
5. Feed mentor evidence into `assumptions.py` (and config if it changes a default).

Note for tests: cleaning facts (corridor count, no " AB" suffixes, determinism, JSON-safe output)
are hard tests. The flip test is a **current-data check**; if mentor evidence changes labels or
`include_facility_events`, update the test and the pitch together, on purpose.

---

## 10. Kill list (until the flip + decision log are polished)

| Defer | Why |
|---|---|
| worst_case / blend modes, mode toggle | Three definitions of risk looks unfinished |
| Recency slider in demo | A second slider muddies the one-slider story |
| `what_would_change` tool | Burns agent time; not needed for the flip |
| Backtest, robustness score | Valuable later; zero if they delay the flip |
| Cause → inspection-type mapping | Looks invented without validation |
| Crew capacity planning | Different product |
| ElevenLabs escalation call | Only after everything above is polished |
| Lab-label toggle in main demo | Only with spare seconds |
| Secondary buyers in pitch | One buyer, one Monday decision |

**Ship floor:** clean data + sum scoring + count-only compare + high-weight slider + flip proof +
likelihood-vs-consequence explanation + `log_decision` + mentor evidence + honesty line.
