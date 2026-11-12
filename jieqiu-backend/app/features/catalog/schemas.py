"""公开目录/成本/日历接口的响应模型（OpenAPI 契约）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MatchItem(BaseModel):
    match_id: str
    match_no: str
    league: str
    home: str
    away: str
    kickoff: str
    sale_close: str
    single: bool
    verdict_id: str | None = None
    status: str | None = None
    rake: float | None = None
    gates: dict[str, str] | None = None
    sp: dict[str, float] | None = None


class MatchListResponse(BaseModel):
    date: str
    count: int
    matches: list[MatchItem]


class VerdictCard(BaseModel):
    id: str
    match_id: str
    match_no: str
    league: str
    home: str
    away: str
    kickoff: str
    pool: str
    goal_line: str
    sp: dict[str, float]
    rake: float
    rake_threshold: float
    probs: dict[str, float]
    pick: dict | None = None
    status: str
    gates: dict[str, str]
    hash: str
    sealed: bool


class VerdictTodayResponse(BaseModel):
    date: str
    stats: dict[str, int]
    items: list[VerdictCard]


class TrueCostResponse(BaseModel):
    match_id: str
    match_no: str
    home: str
    away: str
    pool: str
    goal_line: str
    sp: dict[str, float]
    captured_at: str
    snapshot_count: int
    implied_total: float = Field(description="Σ(1/SP)，含抽水")
    rake: float = Field(description="庄家抽水率 = implied_total - 1")
    rake_pct: float
    fair_probs: dict[str, float]
    fair_odds: dict[str, float]
    ev_per_100: dict[str, float]
    cost_per_100: float
    note: str


class MatchEvidenceResponse(BaseModel):
    match_id: str
    match_no: str
    league: str
    home: str
    away: str
    kickoff: str
    verdict_id: str
    verdict_status: str
    evidence: list[dict]
    data_cutoff: str | None = None
    payload_hash: str
    sealed_at: str | None = None


class AvoidItem(BaseModel):
    verdict_id: str
    match_id: str
    match_no: str
    home: str
    away: str
    league: str
    kickoff: str
    rake: float
    gate: str
    why: str


class AvoidListResponse(BaseModel):
    date: str
    count: int
    items: list[AvoidItem]


class CalendarDay(BaseModel):
    date: str
    matches: int
    verdicts: int
    promoted: int
    screening: int
    killed: int


class CalendarResponse(BaseModel):
    month: str
    total_matches: int
    days: list[CalendarDay]


