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


class AgentResetRequest(BaseModel):
    session_id: str
