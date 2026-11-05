"""推荐主链公开契约。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SnapshotPublic(BaseModel):
    snapshot_id: str
    trade_date: str
    match_id: str
    status: str
    version: int
    payload_hash: str
    published_at: str | None = None
    expires_at: str | None = None
    verdict: dict
    direction: str = "观望"
    confidence: float | None = None
    prob_low: float | None = None
    prob_high: float | None = None
    interval_status: str | None = None
    interval_n: int | None = None
    interval_method: str | None = None
    conditions: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list)
    review: dict | None = None


class PlanPublic(BaseModel):
    plan_id: str
    trade_date: str
    risk_profile: str
    label: str
    legs: list[str]
    status: str
    version: int
    payload_hash: str
    published_at: str | None = None
    expires_at: str | None = None
    check: dict
    note: str | None = None
    conditions: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list)
    review: dict | None = None


class RecommendationToday(BaseModel):
    trade_date: str
    generated_at: str
    snapshots: list[SnapshotPublic]
    plans: list[PlanPublic]
    verdicts: list[dict]
    message: str | None = None
