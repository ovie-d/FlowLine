"""SAMPLE crew types, hazard -> crew -> equipment map, and crew bases.

Everything here is illustrative seed data — "Sample — to be validated" — and is
loaded with is_sample = true. Planners edit it in the UI; the loader never
overwrites rows that already exist.
"""

from __future__ import annotations

from core.taxonomy import (
    CONSTRUCTION_MATERIAL,
    CORROSION_CRACKING,
    EQUIPMENT,
    FIRE_IGNITION,
    GEOTECHNICAL,
    INCORRECT_OPERATION,
    THIRD_PARTY,
    WEATHER,
)

# id -> (name, description)
CREW_TYPES: dict[str, tuple[str, str]] = {
    "civil_erosion": (
        "Civil / erosion-control crew",
        "Washout, scour and right-of-way erosion repair",
    ),
    "electrical_controls": (
        "Electrical & controls technician",
        "Control system, power and instrumentation faults",
    ),
    "fire_response": (
        "Fire & emergency response",
        "Ignition hazards, station fires and emergency isolation",
    ),
    "geotechnical": (
        "Geotechnical crew",
        "Slope movement, frost heave and subsidence assessment",
    ),
    "integrity_dig": (
        "Integrity dig crew",
        "Excavation, assessment and repair of the pipe body",
    ),
    "line_locate": (
        "Line locate & ROW patrol",
        "Locates, right-of-way patrol and third-party activity checks",
    ),
    "mechanical_valve": (
        "Mechanical / valve crew",
        "Valves, seals, gaskets, pumps and compressors",
    ),
    "nde_technician": (
        "NDE technician",
        "Non-destructive examination of pipe and welds",
    ),
    "operations_review": (
        "Operations supervisor",
        "Procedure review, isolation and lockout",
    ),
    "pipe_repair": (
        "Pipe repair crew",
        "Welding, sleeves and clamps after mechanical damage",
    ),
    "weather_response": (
        "Weather / storm response crew",
        "Cold-weather, flood and storm response at stations and ROW",
    ),
}

# hazard group -> [(crew type, equipment list, priority)]
HAZARD_CREW_MAP: dict[str, list[tuple[str, list[str], int]]] = {
    CORROSION_CRACKING: [
        (
            "integrity_dig",
            ["Excavator", "Hydrovac", "Coating repair kit", "Repair sleeves"],
            1,
        ),
        ("nde_technician", ["UT thickness gauge", "Phased-array UT", "MPI kit"], 2),
    ],
    EQUIPMENT: [
        (
            "mechanical_valve",
            ["Valve seal & packing kits", "Spare gaskets", "Torque tools"],
            1,
        ),
        ("electrical_controls", ["Multimeter", "PLC laptop", "Arc-flash PPE"], 2),
    ],
    INCORRECT_OPERATION: [
        ("operations_review", ["Lockout/tagout kit", "Portable gas detector"], 1),
    ],
    THIRD_PARTY: [
        ("line_locate", ["Line locator", "Probe bar", "ROW signage"], 1),
        ("pipe_repair", ["Welding rig", "Repair sleeves / clamps", "Excavator"], 2),
    ],
    GEOTECHNICAL: [
        (
            "geotechnical",
            ["GNSS survey kit", "Inclinometer readout", "Survey drone"],
            1,
        ),
        ("civil_erosion", ["Excavator", "Riprap", "Erosion matting", "Sandbags"], 2),
    ],
    WEATHER: [
        (
            "weather_response",
            ["Portable heaters", "Generator", "Sandbags", "Snow removal"],
            1,
        ),
    ],
    CONSTRUCTION_MATERIAL: [
        ("integrity_dig", ["Excavator", "Hydrovac", "Repair sleeves"], 1),
        ("nde_technician", ["Weld inspection UT", "Radiography (contract)"], 2),
    ],
    FIRE_IGNITION: [
        ("fire_response", ["Foam unit", "Portable gas detectors", "SCBA"], 1),
    ],
}

# id -> (name, province, lat, lon, crew types). Town-centre coordinates.
CREW_BASES: dict[str, tuple[str, str, float, float, list[str]]] = {
    "calgary": (
        "Calgary",
        "Alberta",
        51.0447,
        -114.0719,
        [
            "electrical_controls",
            "fire_response",
            "integrity_dig",
            "line_locate",
            "nde_technician",
        ],
    ),
    "edmonton": (
        "Edmonton",
        "Alberta",
        53.5461,
        -113.4938,
        [
            "electrical_controls",
            "fire_response",
            "integrity_dig",
            "mechanical_valve",
            "nde_technician",
            "operations_review",
            "pipe_repair",
        ],
    ),
    "edson": (
        "Edson",
        "Alberta",
        53.5817,
        -116.4396,
        ["civil_erosion", "geotechnical", "mechanical_valve", "weather_response"],
    ),
    "fort_mcmurray": (
        "Fort McMurray",
        "Alberta",
        56.7268,
        -111.3790,
        ["fire_response", "mechanical_valve", "weather_response"],
    ),
    "grande_prairie": (
        "Grande Prairie",
        "Alberta",
        55.1707,
        -118.7947,
        [
            "civil_erosion",
            "geotechnical",
            "integrity_dig",
            "line_locate",
            "weather_response",
        ],
    ),
    "hardisty": (
        "Hardisty",
        "Alberta",
        52.6745,
        -111.3069,
        ["fire_response", "mechanical_valve", "operations_review", "pipe_repair"],
    ),
    "red_deer": (
        "Red Deer",
        "Alberta",
        52.2681,
        -113.8112,
        ["civil_erosion", "integrity_dig", "line_locate", "pipe_repair"],
    ),
    "whitecourt": (
        "Whitecourt",
        "Alberta",
        54.1416,
        -115.6833,
        ["geotechnical", "mechanical_valve", "nde_technician", "weather_response"],
    ),
}
