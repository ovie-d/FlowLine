"""Live modeling assumptions with validation status."""

from __future__ import annotations

from typing import Any

ASSUMPTIONS: list[dict[str, Any]] = [
    {
        "id": "volume_vs_severity",
        "statement": (
            "Crew priority should trade off incident volume against consequence "
            "severity under an explicit weight, not count alone."
        ),
        "status": "validated",
        "evidence": (
            "Pipeline integrity professional, Oct 3: prioritize serious releases; "
            "do not just count — combine frequency, severity, volume, proximity, "
            "asset type, operating conditions, recency."
        ),
        "affects": ["weights"],
    },
    {
        "id": "facility_events",
        "statement": (
            "Facility fires and limit breaches with no release count toward "
            "corridor priority for pipe walks."
        ),
        "status": "validated",
        "evidence": (
            "Pipeline integrity professional, Oct 3: facility fires / limit "
            "breaches are context and risk indicators, not pipe failures; "
            "keeping a low weight is consistent."
        ),
        "affects": ["include_facility_events"],
    },
    {
        "id": "gas_threshold",
        "statement": "Gas release >= 10,000 m3 is high consequence",
        "status": "validated",
        "evidence": (
            "Pipeline integrity professional, Oct 3: 10,000 m3 is acceptable as "
            "an initial screening threshold; validate against operator incident "
            "classifications in production."
        ),
        "affects": ["gas_high_m3"],
    },
    {
        "id": "injuries_medium",
        "statement": "Serious injuries are at least medium consequence (not low).",
        "status": "unvalidated",
        "evidence": "",
        "affects": ["severity_v2"],
    },
    {
        "id": "edmonton_sherwood",
        "statement": (
            "Edmonton and Sherwood Park are ranked as separate corridors "
            "(including the 'Edmonton & Sherwood Park' label as its own corridor)."
        ),
        "status": "validated",
        "evidence": (
            "Pipeline integrity professional, Oct 3: do not assume Edmonton and "
            "Sherwood Park are the same site without asset IDs / segment metadata."
        ),
        "affects": ["corridor"],
    },
    {
        "id": "triage_escalate_min_high",
        "statement": (
            "Auto-triage escalates a corridor to P1 when it has at least 3 "
            "high-consequence incidents and confidence is ok."
        ),
        "status": "unvalidated",
        "evidence": (
            "Not asked in mentor session. Note: escalate set is identical at "
            "high=3 and high=6 on current seed (Sherwood Park, Edmonton, Hardisty)."
        ),
        "affects": ["ESCALATE_MIN_HIGH"],
    },
]


def get_assumptions() -> list[dict[str, Any]]:
    """Return a copy of live assumptions."""
    return [dict(a) for a in ASSUMPTIONS]


def update_assumption(
    assumption_id: str,
    *,
    status: str | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    """Update one assumption in-place. Returns the row or {error}."""
    for row in ASSUMPTIONS:
        if row["id"] == assumption_id:
            if status is not None:
                if status not in {"validated", "sourced", "unvalidated"}:
                    raise ValueError(f"bad status: {status}")
                row["status"] = status
            if evidence is not None:
                row["evidence"] = evidence
            return dict(row)
    return {"error": f"Unknown assumption: {assumption_id}"}
