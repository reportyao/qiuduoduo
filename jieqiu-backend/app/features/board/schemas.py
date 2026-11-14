from typing import Any

from pydantic import BaseModel, Field


class LiveMatch(BaseModel):
    match_id: str
    match_no: str = ""
    league: str = ""
    home: str = ""
    away: str = ""
    kickoff: str = ""
    state: str = ""
    minute: str = ""
    score_home: int | None = None
    score_away: int | None = None
    ht_home: int | None = None
    ht_away: int | None = None
    updated_at: str | None = None


class LiveBoardResponse(BaseModel):
    date: str
    count: int
    matches: list[LiveMatch]


class ResultMatch(BaseModel):
    match_id: str
    match_no: str = ""
    league: str = ""
    home: str = ""
    away: str = ""
    kickoff: str = ""
    status: str = ""
    score_home: int | None = None
    score_away: int | None = None
    ht_home: int | None = None
    ht_away: int | None = None
    source: str = ""
    # 静默个性化标记：关注/看过/问过，不作为标签展示。
    interest: bool = False


class ResultBoardResponse(BaseModel):
    date: str
    count: int
    matches: list[ResultMatch]


class PredictionHistoryMain(BaseModel):
    label: str = ""
    key: str = ""
    direction: str = ""
    probability: float | None = None
    actual: str = ""
    result: str = ""


class PredictionHistoryMatch(BaseModel):
    match_id: str
    match_no: str = ""
    league: str = ""
    home: str = ""
    away: str = ""
    kickoff: str = ""
    score_home: int | None = None
    score_away: int | None = None
    status: str = ""
    interest: bool = False
    main_prediction: PredictionHistoryMain | None = None
    settled_dimensions: int = 0
    total_dimensions: int = 0


class PredictionAccuracy(BaseModel):
    total_items: int
    settled_items: int
    hit_items: int
    push_items: int
    miss_items: int
    hit_rate: float | None = None


class PerformanceTrendPoint(BaseModel):
    date: str
    settled: int
    hits: int
    rate: float | None = None


class PerformanceMarketRow(BaseModel):
    market: str
    settled: int
    hits: int
    pushes: int = 0
    rate: float | None = None


class CalibrationBucket(BaseModel):
    bucket: str
    predicted: float
    actual: float | None = None
    count: int


class PerformanceResponse(BaseModel):
    days: int
    total_settled: int
    total_hits: int
    hit_rate: float | None = None
    trend: list[PerformanceTrendPoint] = Field(default_factory=list)
    by_market: list[PerformanceMarketRow] = Field(default_factory=list)
    by_league: list[PerformanceMarketRow] = Field(default_factory=list)
    calibration: list[CalibrationBucket] = Field(default_factory=list)


class PredictionHistoryResponse(BaseModel):
    date: str
    summary: PredictionAccuracy
    count: int
    matches: list[PredictionHistoryMatch]


class PredictionSnapshotMeta(BaseModel):
    captured_at: str | None = None
    locked_at: str | None = None
    status: str = ""
    source: str = ""


class PredictionProbability(BaseModel):
    key: str
    label: str = ""
    probability: float


class PredictionSettlementItem(BaseModel):
    source: str
    type: str
    label: str = ""
    predicted_key: str = ""
    predicted_label: str = ""
    predicted_probability: float | None = None
    probabilities: list[PredictionProbability] = Field(default_factory=list)
    market_line: str = ""
    actual_key: str = ""
    actual_label: str = ""
    result: str
    counted_in_accuracy: bool


class PostmatchGoal(BaseModel):
    minute: int | None = None
    player: str = ""
    side: str = ""
    result: str = ""
    # goal / penalty / own_goal（Sportmonks type_id 14/16/15）
    kind: str = ""


class PostmatchData(BaseModel):
    score_home: int | None = None
    score_away: int | None = None
    xg_home: float | None = None
    xg_away: float | None = None
    goals: list[PostmatchGoal] = Field(default_factory=list)
    captured_at: str | None = None


class HalfCheck(BaseModel):
    predicted_ht: str = ""
    actual_ht: str = ""
    on_track: bool | None = None


class PredictionHistoryDetailResponse(BaseModel):
    match_id: str
    match_no: str = ""
    league: str = ""
    home: str = ""
    away: str = ""
    kickoff: str = ""
    score_home: int | None = None
    score_away: int | None = None
    status: str = ""
    snapshot: PredictionSnapshotMeta
    postmatch: PostmatchData | None = None
    half_check: HalfCheck | None = None
    summary: PredictionAccuracy
    items: list[PredictionSettlementItem]


class BoardSyncResponse(BaseModel):
    ok: bool = True
    message: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
