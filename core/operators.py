"""Operator grouping and commodity carried from the CER Pipeline Systems layer.

Commodity comes from the *system* an operator runs (data/cer_pipeline_systems.csv,
fetched by scripts/fetch_pipeline_systems.py), never from the incident's release
fields, so it is known before any incident happens.
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

SYSTEMS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "cer_pipeline_systems.csv"
)

UNKNOWN = "unknown"
OTHER_OPERATOR = "Other operator"

# Incident `Company` spelling -> (operator group, CER systems-layer company or None).
# Alphabetized. Companies absent here fall back to OTHER_OPERATOR / unknown commodity.
OPERATOR_ALIASES: dict[str, tuple[str, str | None]] = {
    "Alliance Pipeline Ltd.": ("Alliance", "Alliance Pipeline Ltd."),
    "Cochin Pipe Lines Ltd.": ("Cochin", "PKM Cochin ULC"),
    "Emera Brunswick Pipeline Company Ltd.": (
        "Brunswick",
        "Emera Brunswick Pipeline Company Ltd.",
    ),
    "Enbridge Pipelines (NW) Inc.": ("Enbridge", "Enbridge Pipelines (NW) Inc."),
    "Enbridge Pipelines Inc.": ("Enbridge", "Enbridge Pipelines Inc."),
    "Enbridge Southern Lights GP Inc. on behalf of Enbridge Southern Lights LP": (
        "Enbridge",
        "Enbridge Southern Lights GP Inc. on behalf of Enbridge Southern Lights LP",
    ),
    "Express Pipeline Ltd.": ("Express", "Express Pipeline Ltd."),
    "Foothills Pipe Lines (Saskatchewan) Ltd.": (
        "Foothills",
        "Foothills Pipe Lines Ltd.",
    ),
    "Foothills Pipe Lines (South B.C.) Ltd.": (
        "Foothills",
        "Foothills Pipe Lines Ltd.",
    ),
    "Foothills Pipe Lines Ltd.": ("Foothills", "Foothills Pipe Lines Ltd."),
    "Kinder Morgan Cochin ULC": ("Cochin", "PKM Cochin ULC"),
    "Kingston Midstream Limited": (
        "Kingston Midstream",
        "Kingston Midstream Westspur Limited",
    ),
    "Many Islands Pipe Lines (Canada) Limited": (
        "Many Islands",
        "Many Islands Pipe Lines (Canada) Limited",
    ),
    "Maritimes & Northeast Pipeline Management Ltd.": (
        "M&NP",
        "Maritimes & Northeast Pipeline Management Ltd.",
    ),
    "Montreal Pipe Line Limited": ("Montreal Pipe Line", "Montreal Pipe Line Limited"),
    "NGTL GP Ltd., as general partner on behalf of NGTL Limited Partnership": (
        "NGTL",
        "NOVA Gas Transmission Ltd.",
    ),
    "NGTL GP Ltd., as general partner, on behalf of NGTL Limited Partnership": (
        "NGTL",
        "NOVA Gas Transmission Ltd.",
    ),
    "NOVA Gas Transmission Ltd.": ("NGTL", "NOVA Gas Transmission Ltd."),
    "Plains Midstream Canada ULC": ("Plains Midstream", "Plains Midstream Canada ULC"),
    "Trans Mountain Pipeline ULC": ("Trans Mountain", "Trans Mountain Pipeline ULC"),
    "Trans Québec and Maritimes Pipeline Inc.": (
        "TQM",
        "Trans Québec and Maritimes Pipeline Inc.",
    ),
    "Trans-Northern Pipelines Inc.": (
        "Trans-Northern",
        "Trans-Northern Pipelines Inc.",
    ),
    "TransCanada Keystone Pipeline GP Ltd.": ("Keystone", "South Bow GP (Canada) Ltd."),
    "TransCanada PipeLines Limited": ("TC Mainline", "TransCanada PipeLines Limited"),
    "TransCanada PipeLines Limited B.C. System": (
        "TC Mainline",
        "TransCanada PipeLines Limited",
    ),
    "Westcoast Energy GP Inc. on behalf of Westcoast Energy Limited Partnership": (
        "Westcoast",
        "Westcoast Energy Inc.",
    ),
    "Westcoast Energy Inc.": ("Westcoast", "Westcoast Energy Inc."),
    "Westcoast Energy Inc., carrying on business as Spectra Energy Transmission": (
        "Westcoast",
        "Westcoast Energy Inc.",
    ),
}


def normalize_company(name: str | None) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip()


@lru_cache(maxsize=1)
def system_commodities() -> dict[str, str]:
    """Systems-layer company -> commodity ('gas' | 'liquid' | 'mixed')."""
    by_company: dict[str, set[str]] = {}
    with SYSTEMS_PATH.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            company = normalize_company(row["company"])
            by_company.setdefault(company, set()).add(row["commodity"].strip().lower())
    return {c: (v.pop() if len(v) == 1 else "mixed") for c, v in by_company.items()}


def operator_group(company: str | None) -> str:
    hit = OPERATOR_ALIASES.get(normalize_company(company))
    return hit[0] if hit else OTHER_OPERATOR


def commodity_carried(company: str | None) -> str:
    """'gas' | 'liquid' | 'mixed' | 'unknown', from the CER systems layer only."""
    hit = OPERATOR_ALIASES.get(normalize_company(company))
    if hit is None or hit[1] is None:
        return UNKNOWN
    return system_commodities().get(normalize_company(hit[1]), UNKNOWN)
