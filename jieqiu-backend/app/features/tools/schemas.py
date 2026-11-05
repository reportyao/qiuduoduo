"""串关体检请求/响应模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..intel.schemas import Coverage, IntelFact


class ParlayLegIn(BaseModel):
    verdict_id: str = Field(min_length=1, max_length=64)
    dir: Literal["home", "draw", "away"]


class ParlayCheckRequest(BaseModel):
    legs: list[ParlayLegIn] = Field(min_length=2, max_length=4)
    stake: float = Field(default=100, ge=1, le=1_000_000)


class ParlayLegOut(BaseModel):
    verdict_id: str
    match_id: str
    match_no: str
    league: str
    home: str
    away: str
    kickoff: str
    dir: str
    dir_label: str
    odds: float
    market_prob: float
    model_prob: float | None = None
    model_edge: float | None = None
    model_expected_return: float | None = None
    model_engine: str | None = None
    rake: float
    status: str
    gates: dict[str, str]
    coverage: Coverage
    facts: list[IntelFact]
    unknowns: list[str]
    sealed: bool
    payload_hash: str | None = None


class ParlayCombo(BaseModel):
    leg_count: int
    odds: float
    market_prob: float
    model_prob: float | None = None
    model_edge: float | None = None
    market_return_rate: float
    model_expected_return: float | None = None
    market_expected_return: float
    cost: float
    cost_pct: float
    model_coverage: str


class ParlayScores(BaseModel):
    cost: str
    info: str
    model: str
    structure: str


class ParlayNote(BaseModel):
    key: str
    level: str
    message: str


class ParlayPlanRequest(BaseModel):
    date: str | None = None
    stake: float = Field(default=100, ge=1, le=1_000_000)
    risk_profiles: list[Literal["conservative", "balanced", "aggressive"]] = Field(
        default_factory=lambda: ["conservative", "balanced", "aggressive"],
        min_length=1, max_length=3)


class ParlayPlanItem(BaseModel):
    label: str
    risk_profile: str
    legs: list[str]
    check: "ParlayCheckResponse"
    note: str | None = None


class ParlayPlanResponse(BaseModel):
    date: str
    candidates: int
    plans: list[ParlayPlanItem]
    message: str | None = None


class ParlayCheckResponse(BaseModel):
    legs: list[ParlayLegOut]
    combo: ParlayCombo
    scores: ParlayScores
    risks: list[ParlayNote]
    optimizations: list[ParlayNote]
    summary: str
    as_of: str
    data_cutoff: str | None = None

ParlayPlanItem.model_rebuild()
