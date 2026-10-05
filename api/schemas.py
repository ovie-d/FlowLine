"""Pydantic request bodies for POST routes."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator


class PolicyParams(BaseModel):
    high: float = 3.0
    medium: float = 1.5
    low: float = 1.0
    count_only: bool = False


class CompareRequest(BaseModel):
    a: PolicyParams = Field(default_factory=PolicyParams)
    b: PolicyParams = Field(default_factory=PolicyParams)
    top: int = 15


class AgentRequest(BaseModel):
    session_id: str
    question: str
    high: float | None = None


class AgentResetRequest(BaseModel):
    session_id: str


class CrewEntry(BaseModel):
    crew_type_id: str = Field(min_length=1, max_length=64)
    equipment: list[str] = Field(default_factory=list)
    priority: int | None = Field(default=None, ge=1, le=20)


class CrewMapUpdate(BaseModel):
    hazard_group: str
    crews: list[CrewEntry] = Field(default_factory=list, max_length=12)


class DispatchRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    hazard_group: str
    k: int = Field(default=3, ge=1, le=10)


class ForecastRequest(BaseModel):
    """Forecast at a point (latitude + longitude) or a ranking corridor by name."""

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    corridor: str | None = Field(default=None, max_length=120)
    date: dt.date | None = None
    operator_group: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _where(self) -> ForecastRequest:
        has_point = self.latitude is not None and self.longitude is not None
        if not has_point and not self.corridor:
            raise ValueError("give latitude and longitude, or a corridor name")
        return self
