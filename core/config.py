"""Risk policy config — every ranking knob lives here."""

from __future__ import annotations

from dataclasses import dataclass, field


def _default_weights() -> dict[str, float]:
    return {"high": 3.0, "medium": 1.5, "low": 1.0}


@dataclass(frozen=True)
class RiskConfig:
    """Explicit risk policy. API/UI/agent only edit this object."""

    weights: dict[str, float] = field(default_factory=_default_weights)
    label: str = "v2"  # "v2" | "lab"
    half_life_years: float | None = None
    include_facility_events: bool = True
    min_incidents_confident: int = 3
    gas_high_m3: float = 10_000.0
    liquid_high_m3: float = 100.0
    count_only: bool = False

    def __post_init__(self) -> None:
        if self.label not in {"v2", "lab"}:
            raise ValueError(f"label must be 'v2' or 'lab', got {self.label!r}")
        if self.half_life_years is not None and self.half_life_years <= 0:
            raise ValueError("half_life_years must be > 0 or None")
        for key in ("high", "medium", "low"):
            if key not in self.weights:
                raise ValueError(f"weights missing {key!r}")
            if self.weights[key] < 0:
                raise ValueError(f"weights[{key!r}] must be >= 0")
        if self.min_incidents_confident < 1:
            raise ValueError("min_incidents_confident must be >= 1")
        if self.gas_high_m3 < 0 or self.liquid_high_m3 < 0:
            raise ValueError("volume thresholds must be >= 0")


BASELINE_COUNT = RiskConfig(count_only=True)

LOW_CONSEQUENCE = RiskConfig(
    weights={"high": 1.5, "medium": 1.5, "low": 1.0},
)

CONSEQUENCE_HEAVY = RiskConfig(
    weights={"high": 6.0, "medium": 1.5, "low": 1.0},
)

DEFAULT = RiskConfig()
