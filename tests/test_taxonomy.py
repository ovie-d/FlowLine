"""Hazard taxonomy — CER detailed codes -> Flowline hazard groups."""

from __future__ import annotations

import pandas as pd
import pytest

from core.taxonomy import (
    CONSTRUCTION_MATERIAL,
    CORROSION_CRACKING,
    EQUIPMENT,
    FIRE_IGNITION,
    GEOTECHNICAL,
    HAZARD_GROUPS,
    HAZARD_LABELS,
    INCORRECT_OPERATION,
    LOW_EVIDENCE_GROUPS,
    MODEL_TARGETS,
    OTHER,
    THIRD_PARTY,
    UNDETERMINED,
    WEATHER,
    all_hazards,
    assign_hazard_groups,
    classify_code,
    primary_hazard,
)

DDM = "Damage or deterioration mechanism, "


@pytest.mark.parametrize(
    ("code", "group"),
    [
        (DDM + "Material Loss, External Material Loss", CORROSION_CRACKING),
        (DDM + "Material Loss, Internal Material Loss", CORROSION_CRACKING),
        (DDM + "Cracking, Stress Corrosion Cracking", CORROSION_CRACKING),
        (DDM + "Structural Degradation, Corrosion Fatigue", CORROSION_CRACKING),
        (DDM + "Equipment, Valve Seals or Packing", EQUIPMENT),
        (DDM + "Other Causes, Control System Malfunction", EQUIPMENT),
        (DDM + "Electrical Power System Failure, Arc Flash", EQUIPMENT),
        (DDM + "External Interference, Third Party", THIRD_PARTY),
        (DDM + "Geotechnical Failure, Frost heave", GEOTECHNICAL),
        (DDM + "Geotechnical Failure, Wash-out or Erosion", GEOTECHNICAL),
        (DDM + "Construction, Defective Circumferential Weld", CONSTRUCTION_MATERIAL),
        (
            DDM + "Material or Manufacturing, Defective Longitudinal Seam Weld",
            CONSTRUCTION_MATERIAL,
        ),
        (DDM + "Other Causes, Improper Operation", INCORRECT_OPERATION),
        (DDM + "Other Causes, Unknown", OTHER),
        ("Substandard Conditions, Weather Related, Lightning", WEATHER),
        ("Substandard Conditions, Fire and explosion hazards", FIRE_IGNITION),
        ("Substandard Conditions, Defective tools, equipment or materials", EQUIPMENT),
        (
            "Substandard Acts, Failure to follow procedure or policy or practice",
            INCORRECT_OPERATION,
        ),
        ("Substandard Conditions, Inadequate guards or barriers", INCORRECT_OPERATION),
    ],
)
def test_classify_code(code: str, group: str) -> None:
    hit = classify_code(code)
    assert hit is not None and hit[0] == group


def test_unknown_code_is_none() -> None:
    assert classify_code("") is None
    assert classify_code("Something new, never seen") is None


def test_physical_mechanism_beats_human_act_regardless_of_order() -> None:
    detailed = (
        "Substandard Acts, Failure to check or monitor;"
        + DDM
        + "Material Loss, External Material Loss"
    )
    assert primary_hazard(detailed, "Corrosion and Cracking") == CORROSION_CRACKING


def test_weather_condition_beats_human_act() -> None:
    detailed = (
        "Substandard Acts, Failure to identify hazard or risk;"
        "Substandard Conditions, Weather Related, Frozen components"
    )
    assert primary_hazard(detailed, "External Interference") == WEATHER


def test_unknown_mechanism_loses_to_any_known_cause() -> None:
    detailed = DDM + "Other Causes, Unknown;Substandard Acts, Improper loading"
    assert primary_hazard(detailed, "Other Causes") == INCORRECT_OPERATION


def test_first_listed_wins_within_tier() -> None:
    detailed = DDM + "Geotechnical Failure, Scouring;" + DDM + "Cracking, Fatigue"
    assert primary_hazard(detailed, None) == GEOTECHNICAL


def test_fallback_to_category_when_no_detail() -> None:
    assert primary_hazard(None, "Equipment Failure, Incorrect Operation") == EQUIPMENT
    assert primary_hazard("", "To be determined") == UNDETERMINED
    assert primary_hazard(None, None) == OTHER


def test_all_hazards_dedupes_in_order() -> None:
    detailed = (
        DDM + "Equipment, Gasket/O-ring;"
        "Substandard Acts, Failure to secure;"
        + DDM
        + "Equipment, Valve Seals or Packing"
    )
    assert all_hazards(detailed) == [EQUIPMENT, INCORRECT_OPERATION]


def test_assign_hazard_groups_aligns_with_index() -> None:
    df = pd.DataFrame(
        {
            "Detailed what happened": [DDM + "Cracking, Fatigue", None],
            "What happened category": [
                "Corrosion and Cracking",
                "Natural Force Damage",
            ],
        },
        index=[10, 20],
    )
    out = assign_hazard_groups(df)
    assert out.to_dict() == {10: CORROSION_CRACKING, 20: GEOTECHNICAL}


def test_every_group_has_a_label() -> None:
    assert set(HAZARD_GROUPS) == set(HAZARD_LABELS)


def test_model_targets_exclude_other_and_undetermined() -> None:
    assert OTHER not in MODEL_TARGETS
    assert UNDETERMINED not in MODEL_TARGETS
    assert len(MODEL_TARGETS) == 8
    assert set(MODEL_TARGETS) < set(HAZARD_GROUPS)


def test_third_party_is_flagged_low_evidence() -> None:
    assert THIRD_PARTY in MODEL_TARGETS
    assert THIRD_PARTY in LOW_EVIDENCE_GROUPS
