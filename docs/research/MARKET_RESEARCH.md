# Market Research — Flowline Hazard Forecast

> Source: product brief (BUILD_PROMPT.md §0). Competitor descriptions are positioning notes,
> not verified product reviews. Validate details with each vendor's public material before
> quoting them in a pitch.

## One-liner

*"Their models tell you how strong the pipe is. Flowline tells you what kind of trouble to
prepare for, and who to send."*

## Where the market is today

Pipeline integrity tooling is built around an operator's **own** asset and inspection data:
in-line inspection (ILI) runs, pipe material and age, coating, pressure, and dig results. These
tools answer an asset question: *how strong is this pipe, and where will it fail first?*

| Player | Type | What it does (positioning) | Data it relies on |
| --- | --- | --- | --- |
| TC Energy — in-house QRA | Operator in-house | Quantitative Risk Assessment across its system | TC's private asset, ILI and operations data |
| TC Energy — Psqr | Operator in-house (award-winning) | Corrosion model; burst pressure from in-line inspection results | ILI anomaly data |
| Dynamic Risk | Third-party software / services | Integrity and risk management for pipeline operators | Operator asset + inspection data |
| C-FER PIRAMID | Third-party software | Reliability-based pipeline risk assessment | Operator asset + inspection data |
| MISTRAS | Third-party services / software | Asset integrity, inspection and NDT services | Operator inspection data |
| irth Solutions | Third-party software | Damage prevention / ticket and field risk management | Operator one-call and field data |

## The gap Flowline fills

None of the above is built to answer an **operational readiness** question from the **whole
industry's public record**:

- *For this area, this season, these conditions — what types of trouble tend to happen?*
- *What happened in similar past incidents?*
- *Which crew and equipment should be ready, and which base gets there fastest?*

Flowline learns from Canada Energy Regulator (CER) public incident history and incident
narratives across all regulated operators. It outputs:

1. A **hazard-type mix** for an area and conditions (e.g. equipment failure vs corrosion vs
   ground movement).
2. **Similar past incidents** as evidence (narrative vector search).
3. **Crew and equipment** mapped to each hazard type.
4. **Dispatch routing** for the matching crew in an emergency.
5. A short **readiness briefing** whose numbers all come from our tools.

## Positioning rules

- Flowline is an **add-on, not a replacement**. It complements QRA, Psqr, and third-party
  integrity platforms; it does not compete with them on pipe strength or failure probability.
- Never claim Flowline certifies pipe safety or outperforms an operator's risk models.
- Flowline uses public data only, so it works across operators and needs no data-sharing
  agreement to start. The trade-off: it does not know a specific pipe's condition.

**Honesty line (UI footer):** *"Forecasts are based on historical public incident data.
Flowline supports engineering judgment; it does not certify any pipe as safe."*
