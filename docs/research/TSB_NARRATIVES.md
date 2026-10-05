# TSB pipeline occurrence summaries — feasibility check

Time-boxed check (≤ 30 min, 2026-10-05). **Nothing is built on this yet.**

## Why we looked

The CER incident file has no free-text narrative: its "Detailed what/why happened"
columns are fixed cause codes (see `docs/DATA_PROFILE.md` §4). Flowline's vector
search is therefore framed as **"ready for operator incident narratives in a pilot"**;
public CER data only has cause codes. This note checks whether a public narrative
source exists that could fill the gap.

## Source

Transportation Safety Board of Canada — Pipeline Occurrence Database System (PODS),
published monthly as open data:
<https://www.tsb.gc.ca/eng/stats/pipeline/data-2.html>

- `PODSdb_MDOTW_VW_OCCURRENCE_PUBLIC.csv` — 3,436 occurrences, 1979-01 → 2026-09,
  117 columns, UTF-8.
- The site returns HTTP 403 to non-browser user agents; a browser `User-Agent` works.
- Licence: not verified in this check. Confirm before redistributing anything.

## What it has

- **`OccSummary`: real free text.** 99.7% filled, 342 characters on average, written by
  the reporting operator, e.g.:
  > *"A leak occurred in a cultivated field on the NPS 6 Sturgeon Lake Lateral. The leak
  > was detected during an aerial patrol on May 11. The leak was at an external corrosion
  > pit 20mm long x 17mm wide…"*
- Occurrence date, province, nearest location (lat/lon of the nearest named place,
  not the site), pipeline operator, facility/pipeline name, product carried.
- 2008 onward: about 1,860 occurrences (TSB counts differ from CER counts year to year).

## Can it be linked to CER incidents?

- **No shared identifier.** Only 1 summary mentions a CER incident number, and 29
  mention "NEB" or "CER" in passing.
- **Probabilistic link** on occurrence date ±1 day + same province + operator-name
  token overlap:

| Rule | CER incidents with a candidate | Exactly one candidate |
|---|---|---|
| date ±1 d + province + within 50 km of TSB nearest location | 1,007 / 2,034 | 930 |
| date ±1 d + province + operator token match | 1,279 / 2,034 | **1,065 (52%)** |

  Of the 1,065 unique links, 380 are in Alberta; 893 fall in ≤ 2021 and 172 in ≥ 2022.
  Median distance between the CER coordinates and the TSB "nearest location" is ~16 km.
  Three spot checks matched (same operator, same event described). **Precision is not
  measured.** There is no ground truth, so a manual audit of ~50 links would be needed.

## Caveats

1. **The summaries describe the cause** ("external corrosion pit", "lightning ignited").
   They are evidence-panel material only. Using them, or their embeddings, for the
   *target* incident would be direct leakage. Even area-history embeddings must use
   strictly earlier incidents (the existing Phase 6 rule).
2. Coverage is about half of CER incidents, and possibly biased toward the
   occurrence types TSB requires to be reported. Unlinked incidents would have no
   narrative.
3. TSB's `NearestLocation` coordinates are a town, not the site, so they can't replace
   CER coordinates.

## Recommendation (not started)

If we want narratives later, add a `tsb_link` table: CER incident id, TSB OccNo,
match rule, match score. Embed `OccSummary` for the evidence panel only, after a
manual precision audit. Until then, the evidence panel uses structured similarity
(decision A), and the UI copy stays: *"Narrative search is ready for operator incident
narratives in a pilot; public CER data only has cause codes."*
