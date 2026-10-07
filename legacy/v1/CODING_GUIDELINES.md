# Tech Wolves — Coding Guidelines (Case 10)

Read with `HANDOFF.md`. HANDOFF says **what** to build; this says **how**.
If the two conflict, HANDOFF wins on product, this wins on code.

---

## 1. Ground rules

1. **One source of truth for scoring.** All risk math lives in `core/scoring.py`.
   Backend, frontend, and agent never re-implement a formula — they call core.
2. **Every modeling choice is a config field.** No magic numbers in functions.
   Weights, thresholds, half-life, mode → `RiskConfig`. If you're typing a number
   that changes the ranking, it belongs in config.
3. **Every assumption is registered.** New threshold or rule → add an entry to
   `assumptions.py` with status `unvalidated` until Immar has evidence.
4. **`main` always runs.** Never push something that breaks `python -m core.deliverables`.
5. **Organizer starter code is a baseline, not a base.** Reproduce its numbers for
   comparison; don't build on its logic.

---

## 2. Python

- Python 3.11. Dependencies: `pandas`, `anthropic`, `fastapi`, `uvicorn`, `pydantic`, `pytest`.
- Type hints on every public function. `from __future__ import annotations` at top of each file.
- `@dataclass(frozen=True)` for configs; create variants with `dataclasses.replace(cfg, ...)`.
- Pure functions in `core/`: input → output, no printing, no file writes, no globals mutated.
  Printing only in `deliverables.py`. File writes only in `log_decision`.
- Load data once: `@lru_cache` on the loader. Never mutate the cached DataFrame — `.copy()` first.
- Paths via `pathlib.Path(__file__).parent`, never hardcoded absolute paths.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `UPPER_CASE` constants.
- Keep functions under ~40 lines. If it's longer, split it.
- Formatting: `ruff format` (or black). Lint: `ruff check`.

---

## 3. Data handling

- Keep raw columns untouched; add derived ones (`corridor_raw` stays, `corridor` is cleaned;
  `severity_lab` stays, `severity_v2` is ours).
- Every cleaning step reports what it did (counts, merges, snaps) into `cleaning_report`.
  Nothing is silently dropped or changed.
- Alias map and junk-name list are module-level constants, alphabetized, one entry per line.
- Use `pd.NA`-safe checks (`pd.notna`) for `release_m3`; empty means nothing released.
- Deterministic everywhere: explicit sort keys + tie-break (score ↓, n_high ↓,
  last_incident ↓, corridor ↑). Same config → same output, every run.

---

## 4. Output contracts

- Everything returned from `core/` is **JSON-serializable**: dicts, lists, str, int, float, bool, None.
  Convert dates to ISO strings, NaN to `None`, numpy types to Python types before returning.
- Round scores to 2 decimals at the output boundary, not mid-calculation.
- Ranking row and compare result shapes are defined in HANDOFF §5. **Changing a field name
  or shape = tell Somrit and Jafar first.** Additive fields are fine without asking.
- Errors return `{"error": "message"}` from core lookups (e.g. unknown corridor) — don't raise
  for user-input problems. Raise only for programmer errors (bad config value).
- Validate config in `RiskConfig.__post_init__`: weights ≥ 0, mode in allowed set,
  half-life > 0 or None.

---

## 5. Agent

- The agent **never computes numbers**. Every number comes from a tool result.
- One function per tool in `agent/tools.py`; tool schemas next to the function they describe.
  Tool names and arg names match core function args where possible.
- Tool results are compact: trim incident lists (≤ 12), drop columns the model doesn't need.
- System prompt in `agent/prompts.py` as a constant — not inline in the loop.
- Loop: max 8 tool steps, then stop with a clear message. Return
  `{"answer", "tool_calls", "history"}`; `tool_calls` is what the UI shows as chips.
- Model name from env var `AGENT_MODEL`; API key from `ANTHROPIC_API_KEY`. Never commit keys.
- `log_decision` only fires on explicit user request; write append-only JSON with UTC timestamp.
- Guardrail phrasing lives in the prompt: no "safe" / "unsafe" claims; flag unvalidated assumptions.

---

## 6. Backend (Somrit)

- FastAPI routes are thin: parse → build `RiskConfig` → call core → return.
  Zero scoring logic in route handlers.
- Pydantic models for request/response bodies; query params map 1:1 to `RiskConfig` fields.
- Agent conversation history stays server-side (in-memory dict keyed by session id);
  it contains SDK objects and must not be sent to the browser.
- CORS open for the hackathon; note it as a known shortcut.
- `GET /health` returns `{"ok": true}` for demo-day sanity checks.

## 7. Frontend (Jafar)

- All numbers displayed come from the API — no client-side recalculation of scores.
- Slider changes debounce (~250 ms) before refetching `/ranking`.
- Low-confidence corridors visibly marked (badge or faded marker).
- Show agent `tool_calls` as chips under each answer — proves it's a real agent.

---

## 8. Testing (minimal but real)

`tests/test_core.py` with pytest. Lock in the numbers we already know:

- Corridor count after cleaning ≈ 111 (update if alias map changes, on purpose).
- No corridor name ending in " AB", " Ab", " Alberta" after cleaning.
- Default config → Edson is rank 1.
- `high=6` → Sherwood Park is rank 1.
- `count_only=True` reproduces the organizer baseline top 15.
- Same config twice → identical output (determinism).
- Every ranking row passes `json.dumps` without a custom encoder.

Run `pytest -q` before every push to `main`.

---

## 9. Git workflow (48-hour version)

- Branch per lane: `core/…`, `backend/…`, `frontend/…`. Merge to `main` often (small PRs or direct merges after tests pass).
- Commit messages: `core: add worst_case mode`, `api: /compare route`, `ui: weight slider`.
- Don't commit: API keys, `.env`, the full national CER file, `inspection_decisions.json`, `__pycache__`.
- Feature freeze Saturday night per team plan; after that only bug fixes and demo polish.

---

## 10. Rules for Cursor

- Follow HANDOFF.md for structure and contracts; follow this file for style.
- Don't modify files outside the task you were asked to do.
- Don't rename public functions or output fields without being told to.
- Don't introduce new dependencies without asking.
- When adding a threshold, weight, or rule: add it to `RiskConfig` and register it in `assumptions.py`.
- After changing `core/`, run `python -m core.deliverables` and `pytest -q` and show the output.
- Prefer small, reviewable diffs over rewrites.
