"""Tech Wolves Case 10 — pipeline incident risk core."""

from __future__ import annotations

__all__ = [
    "RiskConfig",
    "compare",
    "get_assumptions",
    "load_incidents",
    "score",
]

from core.assumptions import get_assumptions
from core.compare import compare
from core.config import RiskConfig
from core.data import load_incidents
from core.scoring import score
