# Q&A prep — likely engineer questions, short honest answers

All numbers are from `docs/MODEL_REPORT.md` / `models/hazard_forecast.eval.json`
(evaluation run 2026-10-05). Held-out test = CER incidents from 2022 onward that the
model never saw; it was trained on national incidents up to 2021. Log loss: lower is
better. Brackets are 95% bootstrap confidence intervals. If the data or model is
re-run, re-check these numbers before presenting.

---

### "How accurate is it?"
It forecasts a **mix** of hazard types, not a single answer. On 430 held-out incidents
across Canada, the actual hazard type was in Flowline's top 3 for **72%** of them
(0.72 [0.67, 0.76]) versus **66%** for the best simple history baseline; its single
top pick was right **36%** of the time versus **22%**. In Alberta (164 incidents): top-3
**65%** vs **57%**.

### "Is it better than just looking at incident history?"
Across Canada, **yes, clearly**: log loss 1.794 vs 1.948 for the best simple baseline
(province base rate), an improvement of −0.154 [−0.198, −0.109]. In Alberta the gain is
**real but narrow**: −0.081 [−0.139, −0.022], about half the national gain. Year by year
(each year predicted only from earlier years), it beat the national base rate in 2020,
2021, 2022, 2023 and 2025; in 2024 (64 incidents) the difference was not measurable.

### "Does it work for NGTL?"
**Not yet, honestly.** On NGTL's 122 held-out incidents the model is **not
distinguishable** from the simple baseline (−0.037 [−0.107, +0.028]). Outside NGTL it is
clearly better (−0.183 [−0.241, −0.125]). Public data alone isn't enough for NGTL's
dense, station-heavy system — which is exactly why a pilot with operator data matters.

### "Is it just learning each operator's reporting habits?"
Mostly no. Removing the operator makes **no measurable difference** across Canada
(−0.010 [−0.027, +0.009]), and a model with **no operator, province or commodity** —
only where, when in the year, and what happened nearby before — still beats the best
baseline (−0.139 [−0.185, −0.091]). The data can't fully separate asset type from
reporting practice, so operator-driven differences should be read as "this operator's
history looks like this", not as a physical cause.

### "Why doesn't weather change the forecast?"
We tested it. Adding station weather (temperature, precipitation, freeze–thaw) made
**no measurable difference** (Canada +0.003 [−0.022, +0.029]), so we took it out of the
model rather than show sliders that don't do anything real. Weather stays as context
(Open-Meteo outlook, similar-incident search, briefings). There *is* an observed
pattern — since 2022, washouts and ground movement rose from 8.5% to 22.0% of Alberta
incidents (2.6×) and followed wetter months (median 34.9 mm vs 18.5 mm prior-30-day
rain) — but the model can't learn it from the earlier years, when such incidents were
rare. It's shown as an observed pattern, not a forecast.

### "What would help with washouts?" — pilot talking point
Location matters more than weather so far. Using OpenStreetMap rivers and streams
crossed by CER pipelines, washout/ground-movement incidents before 2022 sat closer to a
pipeline–waterway crossing than other incidents: **44% vs 27% within 2 km** (median 2.2
vs 3.5 km). That rests on only **48 washouts**, so it's **suggestive, not proof** — and
it isn't a model input. An operator's own water-crossing and geohazard inventory would
let a pilot test it properly.

### "How do you know there's no data leakage?"
- **Time split:** trained on ≤ 2021, tested on 2022+; tuning decisions use only the last
  training year.
- **Strictly earlier history:** area-history features use incidents *before* the date,
  and a past incident's cause only counts once it was **closed** (known) by then.
- **Fields recorded because of the outcome are banned:** we tested every candidate
  field's *missingness* against the hazard type. Pipe attributes, facility fields,
  released substance, kilometre post, regulation, and even "was the occurrence date
  recorded" all leak the answer (e.g. the occurrence date is missing for 78% of
  geotechnical incidents but as few as 4.5% for other hazard types) — none are used.
- **Commodity** comes from the CER pipeline-systems layer, not the release record.
- Automated tests assert no future data, no same-day data, and that an incident's own
  label never affects its own features.

### "Where are the incident narratives / vector search?"
Public CER data has **cause codes only**, no written narratives — embedding the codes
would just re-encode the answer. Similar incidents are matched on place, season,
weather and commodity instead. The narrative pipeline (local embeddings, pgvector) is
built and **ready for operator incident narratives in a pilot**. TSB occurrence
summaries could be linked for about half of CER incidents, but that link isn't audited
yet.

### "Which hazards does it miss?"
Rare ones. Third-party damage, fire/ignition and construction defects are almost never
the single top pick (top-1 recall 0 on the test set). In the Alberta test period it
**under-forecast** ground movement/washout (11% predicted vs 22% actual) and
third-party damage (3% vs 8%), and **over-forecast** corrosion & cracking (14% vs 6%)
and construction defects (9% vs 2%).

### "What does '>50%, lower certainty' mean?"
On held-out data the model was overconfident above 50%: 4 forecasts went above 50% and
none came true. So we never show a confident number there.

### "What does 'low evidence base' mean?"
Fewer than 3 earlier incidents within 25 km. The mix is then driven mostly by
location, season and operator, not local history — treat it as indicative.

### "Are the crews, equipment and bases real?"
**No — sample data, labelled "Sample — to be validated" everywhere.** The table is
editable; a pilot would replace it with the operator's real crews, equipment and bases.

### "Can it tell me a pipe is safe?"
No. Flowline forecasts what *kind* of trouble to prepare for from public incident
history. It does not certify any pipe as safe and doesn't replace integrity models such
as TC Energy's QRA or Psqr — it's an add-on for readiness.

### "Does the AI make up numbers?"
The agent can only answer through tools that query the database, model and router;
every number in its answer is checked against the tool results, and any that don't
match are flagged in the UI. Spend is capped and logged.

### "Does routing work without internet?"
Yes, within Alberta: OSRM runs locally on OpenStreetMap data. Remote sites report the
off-road "last mile" separately. If OSRM is down it falls back to Mapbox (with a token),
then to straight-line distance with no drive time and a clear warning.

---

### "What would a pilot need from TC Energy?"
1. **Incident narratives** (what happened / why, as written) for NGTL and other
   systems — turns on narrative similarity and, most likely, improves NGTL.
2. **Asset attributes from the asset register** (not from incident reports): pipe
   material, diameter, install year, coating, MOP, facility inventory (compressor and
   meter stations). Taken independently of incidents, they're usable without leakage.
3. **Inspection and maintenance history** (ILI anomaly summaries, dig results, recent
   maintenance) as of each date.
4. **Geohazard inventory** (slopes, water crossings, ROW erosion sites) — the most
   direct lever for the washout trend.
5. **Real crews, equipment and base locations** to replace the sample table.
6. **Near-miss / non-reportable events** to enlarge the sparse classes.
7. An **agreed evaluation**: rolling-origin on TC's own history, judged against the same
   simple baselines, before anyone relies on it.
