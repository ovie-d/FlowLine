# Washout watch — result

Run 2026-10-05 18:50 UTC by `scripts/washout_watch.py`. Backlog item, 3-hour time box. **Judged only on rolling origins with test years 2016–2021** (each trained on earlier years); the 2022+ test set was not used.

## Candidate features

- **Rainfall anomaly**: prior-30-day station rain minus / divided by the station's median for the same window in the 10 years before the incident (≥ 3 valid years). Coverage: 86.7% of target incidents.

- **Waterway crossings**: distance to the nearest pipeline–waterway crossing and crossings within 10 km (Alberta OSM rivers/streams/canals × CER pipeline systems). Coverage: 35.4% (Alberta only; elsewhere missing, never zero).

## Decision rule (fixed before running)

Adopt a feature set only if the pooled paired-bootstrap Δ log loss (with − without) has its 95% CI entirely below 0 **and** no single origin year is measurably worse.

## Result (689 incidents pooled over 6 origins)

Δ log loss = with − deployed (negative = the feature helps), 95% CI.

| candidate | Δ pooled (Canada) | Δ pooled (Alberta) | mean p(geotech) on actual geotech, deployed → with | decision |
|---|---|---|---|---|
| + rainfall anomaly | -0.005 [-0.023, +0.014] | -0.004 [-0.031, +0.024] | 10.2% → 9.7% | drop |
| + waterway crossings | -0.005 [-0.023, +0.011] | -0.030 [-0.059, +0.002] | 10.2% → 9.9% | drop |
| + both | -0.004 [-0.023, +0.015] | -0.022 [-0.056, +0.013] | 10.2% → 10.1% | drop |

### Per origin year (Canada)

| candidate | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 |
|---|---|---|---|---|---|---|
| + rainfall anomaly | +0.035 [-0.005, +0.076] | -0.020 [-0.061, +0.022] | -0.014 [-0.057, +0.028] | +0.023 [-0.026, +0.069] | -0.039 [-0.082, -0.001] | -0.007 [-0.046, +0.032] |
| + waterway crossings | -0.010 [-0.047, +0.027] | -0.049 [-0.086, -0.011] | +0.043 [-0.005, +0.089] | +0.013 [-0.029, +0.056] | -0.036 [-0.074, +0.005] | +0.015 [-0.016, +0.049] |
| + both | +0.011 [-0.035, +0.059] | -0.023 [-0.073, +0.025] | +0.059 [+0.014, +0.107] | -0.007 [-0.060, +0.045] | -0.028 [-0.074, +0.016] | -0.038 [-0.077, +0.002] |

## Conclusion

No candidate met the rule. The washout features are **dropped**; the descriptive finding stays as the UI insight card (GET /insights/washout), labelled as an observed pattern, not a forecast. Alberta-only results are shown for information: under the rule they cannot adopt a feature, and none of their intervals excludes zero either. The crossing-distance pattern (washouts closer to pipeline–waterway crossings before 2022) is kept as an observed, suggestive finding for a pilot — see docs/QA_PREP.md.
