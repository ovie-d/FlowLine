"""Map CER cause codes to Flowline hazard groups (approved 2026-10-05).

The CER's top-level "What happened category" is too coarse for crew planning
(e.g. "External Interference" mixes fire hazards, floods and third-party hits),
so the primary group comes from "Detailed what happened": a ';'-separated list
of hierarchical codes like "Damage or deterioration mechanism, Cracking, Fatigue".

Primary group rule (deterministic):
1. Physical damage mechanisms win over conditions, which win over human acts.
2. Within a tier, the first-listed code wins (CER entry order).
3. No usable detailed code -> fall back to the top-level category.

Other / unknown and Undetermined are stored and shown as evidence, but are not
forecast targets (MODEL_TARGETS).
"""

from __future__ import annotations

import pandas as pd

CORROSION_CRACKING = "corrosion_cracking"
EQUIPMENT = "equipment_failure"
INCORRECT_OPERATION = "incorrect_operation"
THIRD_PARTY = "third_party_damage"
GEOTECHNICAL = "geotechnical"
WEATHER = "natural_forces_weather"
CONSTRUCTION_MATERIAL = "construction_material_defect"
FIRE_IGNITION = "fire_ignition"
OTHER = "other_unknown"
UNDETERMINED = "undetermined"  # still under investigation

# Forecast classes, in display order.
MODEL_TARGETS: tuple[str, ...] = (
    CORROSION_CRACKING,
    EQUIPMENT,
    INCORRECT_OPERATION,
    THIRD_PARTY,
    GEOTECHNICAL,
    WEATHER,
    CONSTRUCTION_MATERIAL,
    FIRE_IGNITION,
)

# Every group an incident can be assigned (stored in the database).
HAZARD_GROUPS: tuple[str, ...] = (*MODEL_TARGETS, OTHER, UNDETERMINED)

# Groups with too little history to forecast with confidence (flag in the UI).
LOW_EVIDENCE_GROUPS: frozenset[str] = frozenset({THIRD_PARTY})

HAZARD_LABELS: dict[str, str] = {
    CORROSION_CRACKING: "Corrosion & cracking",
    EQUIPMENT: "Equipment & component failure",
    INCORRECT_OPERATION: "Incorrect operation / procedures",
    THIRD_PARTY: "Third-party & mechanical damage",
    GEOTECHNICAL: "Ground movement, washout & geotechnical",
    WEATHER: "Natural forces & weather",
    CONSTRUCTION_MATERIAL: "Construction & material defects",
    FIRE_IGNITION: "Fire / ignition hazard",
    OTHER: "Other / unknown",
    UNDETERMINED: "Undetermined (under investigation)",
}

DAMAGE_PREFIX = "Damage or deterioration mechanism, "

# Tier 1 — damage mechanism: "<level 2>[, <level 3>]" -> group. Level-3 overrides first.
DAMAGE_DETAIL_MAP: dict[str, str] = {
    "Other Causes, Control System Malfunction": EQUIPMENT,
    "Other Causes, Improper Operation": INCORRECT_OPERATION,
    "Other Causes, Unknown": OTHER,
    "Structural Degradation, Corrosion Fatigue": CORROSION_CRACKING,
}
DAMAGE_LEVEL2_MAP: dict[str, str] = {
    "Construction": CONSTRUCTION_MATERIAL,
    "Cracking": CORROSION_CRACKING,
    "Electrical Power System Failure": EQUIPMENT,
    "Equipment": EQUIPMENT,
    "External Interference": THIRD_PARTY,
    "Geotechnical Failure": GEOTECHNICAL,
    "Material Loss": CORROSION_CRACKING,
    "Material or Manufacturing": CONSTRUCTION_MATERIAL,
    "Structural Degradation": CONSTRUCTION_MATERIAL,
}

# Tier 2 — specific substandard conditions (weather, ignition, defective tools).
CONDITION_MAP: dict[str, str] = {
    "Substandard Conditions, Defective tools": EQUIPMENT,
    "Substandard Conditions, Fire and explosion hazards": FIRE_IGNITION,
    "Substandard Conditions, Weather Related": WEATHER,
}

# Tier 3 — any other substandard act / condition is a human / procedural cause.
HUMAN_PREFIXES: tuple[str, ...] = ("Substandard Acts", "Substandard Conditions")

# Fallback when no detailed code is usable.
CATEGORY_FALLBACK: dict[str, str] = {
    "Corrosion and Cracking": CORROSION_CRACKING,
    "Defect and Deterioration": CONSTRUCTION_MATERIAL,
    "Equipment Failure": EQUIPMENT,
    "External Interference": THIRD_PARTY,
    "Incorrect Operation": INCORRECT_OPERATION,
    "Natural Force Damage": GEOTECHNICAL,
    "Other Causes": OTHER,
    "To be determined": UNDETERMINED,
}

# Tier rank for each group *as produced by a given code* (lower wins).
_TIER_DAMAGE, _TIER_CONDITION, _TIER_HUMAN, _TIER_UNKNOWN = 1, 2, 3, 4


def classify_code(code: str) -> tuple[str, int] | None:
    """Map one detailed code to (group, tier); None if unrecognised."""
    code = code.strip()
    if not code:
        return None
    if code.startswith(DAMAGE_PREFIX):
        rest = code[len(DAMAGE_PREFIX) :]
        for key, group in DAMAGE_DETAIL_MAP.items():
            if rest.startswith(key):
                tier = _TIER_UNKNOWN if group == OTHER else _TIER_DAMAGE
                if group == INCORRECT_OPERATION:
                    tier = _TIER_HUMAN
                return group, tier
        level2 = rest.split(", ")[0]
        if level2 in DAMAGE_LEVEL2_MAP:
            return DAMAGE_LEVEL2_MAP[level2], _TIER_DAMAGE
        return None
    for prefix, group in CONDITION_MAP.items():
        if code.startswith(prefix):
            return group, _TIER_CONDITION
    if code.startswith(HUMAN_PREFIXES):
        return INCORRECT_OPERATION, _TIER_HUMAN
    return None


def primary_hazard(detailed_what: str | None, category: str | None) -> str:
    """Primary hazard group for one incident."""
    best: tuple[int, str] | None = None
    for code in str(detailed_what or "").split(";"):
        hit = classify_code(code)
        if hit is not None and (best is None or hit[1] < best[0]):
            best = (hit[1], hit[0])
    if best is not None:
        return best[1]
    first_cat = str(category or "").split(",")[0].strip()
    return CATEGORY_FALLBACK.get(first_cat, OTHER)


def all_hazards(detailed_what: str | None) -> list[str]:
    """Every distinct group named by an incident's codes, in first-seen order."""
    seen: list[str] = []
    for code in str(detailed_what or "").split(";"):
        hit = classify_code(code)
        if hit is not None and hit[0] not in seen:
            seen.append(hit[0])
    return seen


def assign_hazard_groups(df: pd.DataFrame) -> pd.Series:
    """Vector helper over a raw CER frame -> primary hazard group per row."""
    return pd.Series(
        [
            primary_hazard(d if pd.notna(d) else None, c if pd.notna(c) else None)
            for d, c in zip(df["Detailed what happened"], df["What happened category"])
        ],
        index=df.index,
        name="hazard_group",
    )
