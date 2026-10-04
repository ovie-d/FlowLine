"""Build RiskConfig from API query/body params — one helper for all routes."""

from __future__ import annotations

from core.config import BASELINE_COUNT, RiskConfig


def config_from_params(
    high: float = 3.0,
    medium: float = 1.5,
    low: float = 1.0,
    count_only: bool = False,
) -> RiskConfig:
    """Map slider/policy params to a RiskConfig.

    Left end of the slider (high == 1) and count_only both mean pure frequency
    via BASELINE_COUNT. Bad values raise ValueError (API maps to 422).
    """
    if count_only or high == 1:
        return BASELINE_COUNT
    return RiskConfig(
        weights={"high": float(high), "medium": float(medium), "low": float(low)}
    )
