"""公开响应模型：聚焦卡 / 数据脉搏 / 互动。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PulseCounts(BaseModel):
    matches: int
    sp_snapshots: int
    intl_odds: int
    model_runs: int
    verdicts: int
    revisions: int
    intel_items: int
    sealed_links: int
    lineups: int
    injuries: int
    standings: int


class PulseDisplay(BaseModel):
    data_points: int
    factor: float
    unit: str


class PulseAllTime(BaseModel):
    data_points: int
    matches: int
    sealed: int


class PulseStage(BaseModel):
    key: str
    label: str
    count: int
    status: str


class PulseSource(BaseModel):
    key: str
    label: str
    status: str
    last_sync: str | None = None
    coverage: float


class PulseOutcomes(BaseModel):
    promoted: int
    screening: int
    killed: int


class PulseResponse(BaseModel):
    trade_date: str
    as_of: str
    stale_seconds: int | None = None
    counts: PulseCounts
    data_points: int
    display: PulseDisplay
    all_time: PulseAllTime
    stages: list[PulseStage]
    sources: list[PulseSource]
    outcomes: PulseOutcomes
    excluded: int
    definition: str


class FocusMatch(BaseModel):
    match_id: str
    match_no: str
    league: str
    home: str
    away: str
    kickoff: str
    sale_close: str
    single: bool


class FocusVerdict(BaseModel):
    id: str
    status: str
    pick: dict[str, Any] | None = None
    rake: float
    rake_threshold: float
    probs: dict[str, float]
    model: dict[str, Any] | None = None
    gates: dict[str, str | None]
    payload_hash: str | None = None
    sealed: bool


class Seal(BaseModel):
    hash: str | None = None
    sealed_at: str | None = None
    revision: int


class CoverageSource(BaseModel):
    key: str
    status: str
    last_sync: str | None = None
    coverage: float


class Coverage(BaseModel):
    score: int
    level: str
    deep_eligible: bool
    missing: list[str]
    sources: list[CoverageSource]
    minutes_to_close: int | None = None
    hours_to_kickoff: int | None = None


class IntelFact(BaseModel):
    id: str
    kind: str
    label: str
    value: str
    detail: str = ""
    source: str | None = None
    captured_at: str | None = None
    status: str
    confidence: float | None = None


class Intel(BaseModel):
    facts: list[IntelFact]
    unknowns: list[str]


class Capabilities(BaseModel):
    can_bet: bool
    bet_requires_confirm: bool
    can_watch: bool
    watching: bool
    can_why_not: bool
    can_view_detail: bool
    can_share: bool
    can_rest: bool
    can_remind_lineup: bool
    can_refresh: bool


class FocusAction(BaseModel):
    id: str
    enabled: bool
    primary: bool
    requires_auth: bool
    reason: str | None = None


class FocusResponse(BaseModel):
    match: FocusMatch
    verdict: FocusVerdict | None = None
    state: str
    trade_date: str
    request_id: str
    as_of: str
    data_cutoff: str | None = None
    seal: Seal
    coverage: Coverage
    intel: Intel
    interpretation: dict[str, Any] | None = None
    capabilities: Capabilities
    actions: list[FocusAction]
    persona: str


class InteractionResponse(BaseModel):
    ok: bool
    duplicate: bool
