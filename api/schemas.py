"""Pydantic request bodies for POST routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
