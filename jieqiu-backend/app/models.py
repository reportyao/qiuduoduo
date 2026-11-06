"""ORM 模型 · W2 核心表（对应 TechSpec §5：sp_matches / sp_snapshots / team_aliases / matches / verdicts / model_runs）。

设计约定：
- 竞彩相关时间一律存中国标准时间的 ISO 字符串（源数据即如此），不做时区换算存储。
- verdicts.payload 为规范化 JSON（sort_keys），payload_hash = sha256(canonical payload)，
  任何人可独立复算验证 —— 这是产品主张（TechSpec §3 封存纪律）。
"""
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, Index, Integer, String,
                        Text, UniqueConstraint, text)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    """naive UTC：所有 DateTime 列统一存无时区 UTC，避免 Postgres 会话时区改写。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SPMatch(Base):
    """竞彩在售/在赛场次（来自采集器 matches 表，队名经过对齐）。"""

    __tablename__ = "sp_matches"

    match_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    match_no: Mapped[str] = mapped_column(String(16), index=True)
    league: Mapped[str] = mapped_column(String(64), default="")
    home_raw: Mapped[str] = mapped_column(String(128), default="")
    away_raw: Mapped[str] = mapped_column(String(128), default="")
    home: Mapped[str] = mapped_column(String(128), default="", index=True)  # 对齐后
    away: Mapped[str] = mapped_column(String(128), default="", index=True)  # 对齐后
    kickoff: Mapped[str] = mapped_column(String(32), index=True)  # "YYYY-MM-DD HH:MM:SS" CN
    single_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SPSnapshot(Base):
    """竞彩 SP 快照（追加式，主键去重）。"""

    __tablename__ = "sp_snapshots"
    __table_args__ = (UniqueConstraint("match_id", "pool", "captured_at", name="uq_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(32), index=True)
    pool: Mapped[str] = mapped_column(String(8))  # had / hhad
    goal_line: Mapped[str] = mapped_column(String(8), default="")
    sp_h: Mapped[float] = mapped_column(Float)
    sp_d: Mapped[float] = mapped_column(Float)
    sp_a: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[str] = mapped_column(String(32), index=True)  # ISO CN


class TeamAlias(Base):
    """球队别名：alias（归一化后）→ canonical 中文名。"""

    __tablename__ = "team_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # 归一化形式
    canonical: Mapped[str] = mapped_column(String(128), index=True)
    lang: Mapped[str] = mapped_column(String(8), default="zh")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Verdict(Base):
    """判决：一场比赛过闸结果的封存记录。状态机 screening → promoted / killed。"""

    __tablename__ = "verdicts"
    __table_args__ = (
        Index("ix_verdicts_trade_status_rake", "trade_date", "rake", "status"),
        Index("ix_verdicts_match_trade", "match_id", "trade_date"),
        Index("ix_verdicts_trade_kickoff", "trade_date", "kickoff"),
        Index("ix_verdicts_status_settled_kickoff", "status", "kickoff", "settled"),
        Index("ix_verdicts_settled_at", "settled_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # v{trade_date}-{match_no}
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # CN 日期 YYYY-MM-DD
    match_id: Mapped[str] = mapped_column(String(32), index=True)
    match_no: Mapped[str] = mapped_column(String(16))
    league: Mapped[str] = mapped_column(String(64))
    home: Mapped[str] = mapped_column(String(128))
    away: Mapped[str] = mapped_column(String(128))
    kickoff: Mapped[str] = mapped_column(String(32))
    pool: Mapped[str] = mapped_column(String(8))  # 评估的玩法池 had / hhad
    goal_line: Mapped[str] = mapped_column(String(8), default="")
    # 价闸产物
    sp_h: Mapped[float] = mapped_column(Float)
    sp_d: Mapped[float] = mapped_column(Float)
    sp_a: Mapped[float] = mapped_column(Float)
    rake: Mapped[float] = mapped_column(Float)          # 0.092 = 9.2%
    p_home: Mapped[float] = mapped_column(Float)        # 去水后
    p_draw: Mapped[float] = mapped_column(Float)
    p_away: Mapped[float] = mapped_column(Float)
    # 模闸产物（收缩后模型概率；无模型预测时为空）
    model_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    pick: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"dir","sp","ev","prob"}
    rake_threshold: Mapped[float] = mapped_column(Float, default=0.126)  # 当日动态阈值快照
    # W4 结算
    settled: Mapped[str | None] = mapped_column(String(8), nullable=True)  # win / lose / null
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_score: Mapped[str | None] = mapped_column(String(12), nullable=True)  # "2-1"
    # CLV：入场 SP vs 停售前最后一条同池快照；clv = 收盘隐含概率 - 入场隐含概率
    closing_sp_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_sp_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_sp_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clv: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 状态与闸门
    status: Mapped[str] = mapped_column(String(16), default="screening", index=True)
    gates: Mapped[dict] = mapped_column(JSON, default=dict)  # {"price": {...}, "market": {...}, "model": {...}}
    payload: Mapped[dict] = mapped_column(JSON)              # 封存的规范化载荷
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IntlOdds(Base):
    """国际盘快照（the-odds-api 等）：已对齐到规范中文队名，供市闸离散度计算。"""

    __tablename__ = "intl_odds"
    __table_args__ = (UniqueConstraint("source", "home", "away", "kickoff_utc",
                                       name="uq_intl_odds"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(24), index=True)  # pinnacle / consensus
    sport: Mapped[str] = mapped_column(String(40), default="")
    league: Mapped[str] = mapped_column(String(64), default="")
    home_raw: Mapped[str] = mapped_column(String(128), default="")
    away_raw: Mapped[str] = mapped_column(String(128), default="")
    home: Mapped[str] = mapped_column(String(128), index=True)  # 规范中文
    away: Mapped[str] = mapped_column(String(128), index=True)
    kickoff_utc: Mapped[str] = mapped_column(String(32), index=True)  # ISO8601 UTC
    sp_h: Mapped[float] = mapped_column(Float)
    sp_d: Mapped[float] = mapped_column(Float)
    sp_a: Mapped[float] = mapped_column(Float)
    retrieved_at: Mapped[str] = mapped_column(String(32), index=True)


class VerdictRevision(Base):
    """判决修订史（追加式）：同一 verdict 随 SP 更新重建时，每个不同 payload 都留档。

    承诺：任何时刻贴出的封存哈希，赛后都能在修订史里找到对应原文并独立复算。
    """

    __tablename__ = "verdict_revisions"
    __table_args__ = (
        UniqueConstraint("verdict_id", "payload_hash", name="uq_revision"),
        Index("ix_verdict_revisions_verdict_created", "verdict_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verdict_id: Mapped[str] = mapped_column(String(40), index=True)
    trade_date: Mapped[str | None] = mapped_column(String(10), index=True)  # 冗余检索列（W6 深审查）
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    data_cutoff: Mapped[str] = mapped_column(String(32), default="")
    chain_prev: Mapped[str] = mapped_column(String(72), default="")   # 前一链节（或前日锚根/GENESIS）
    chain_hash: Mapped[str] = mapped_column(String(72), default="", index=True)  # sha256(prev+payload_hash+ts)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DailyAnchor(Base):
    """当日锚点：把当日全部链节哈希折叠成一个根哈希，锚与锚之间再链成跨日链。

    当日锚点为临时（随修订追加刷新）；次日冻结。
    """

    __tablename__ = "daily_anchors"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    root_hash: Mapped[str] = mapped_column(String(72), index=True)
    revision_count: Mapped[int] = mapped_column(Integer)
    prev_root: Mapped[str] = mapped_column(String(72), default="")  # 前一日锚根 / GENESIS
    built_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MatchResult(Base):
    """赛果（football-data 等源），供判决结算与公开账本。"""

    __tablename__ = "match_results"
    __table_args__ = (UniqueConstraint("home", "away", "match_date", name="uq_result"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(24), default="football-data")
    league: Mapped[str] = mapped_column(String(64), default="")
    home_raw: Mapped[str] = mapped_column(String(128), default="")
    away_raw: Mapped[str] = mapped_column(String(128), default="")
    home: Mapped[str] = mapped_column(String(128), index=True)
    away: Mapped[str] = mapped_column(String(128), index=True)
    match_date: Mapped[str] = mapped_column(String(10), index=True)  # 欧洲当地日期
    goals_home: Mapped[int] = mapped_column(Integer)
    goals_away: Mapped[int] = mapped_column(Integer)
    retrieved_at: Mapped[str] = mapped_column(String(32), default="")


class ApiFootballFixture(Base):
    """API-Football fixture 快照；match_id 为空表示未链接到竞彩场次。"""

    __tablename__ = "api_football_fixtures"
    __table_args__ = (
        Index("ix_af_fixtures_kickoff", "kickoff_utc"),
        Index("ix_af_fixtures_league_season", "league_id", "season"),
        Index("ix_af_fixtures_match", "match_id"),
    )

    fixture_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    league_id: Mapped[int] = mapped_column(Integer, default=0)
    league_name: Mapped[str] = mapped_column(String(128), default="")
    season: Mapped[int] = mapped_column(Integer, default=0)
    home_team_id: Mapped[int] = mapped_column(Integer, default=0)
    home_name: Mapped[str] = mapped_column(String(128), default="")
    away_team_id: Mapped[int] = mapped_column(Integer, default=0)
    away_name: Mapped[str] = mapped_column(String(128), default="")
    kickoff_utc: Mapped[str] = mapped_column(String(32), default="")
    status_short: Mapped[str] = mapped_column(String(8), default="")
    status_long: Mapped[str] = mapped_column(String(32), default="")
    venue: Mapped[str] = mapped_column(String(128), default="")
    link_method: Mapped[str] = mapped_column(String(16), default="none")  # auto/manual/none
    link_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    lineups_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    injuries_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MatchLineup(Base):
    """API-Football 首发/替补；side=home/away 便于 focus 直接展示。"""

    __tablename__ = "match_lineups"
    __table_args__ = (
        UniqueConstraint("fixture_id", "team_id", name="uq_lineup_fixture_team"),
        Index("ix_lineups_match", "match_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, index=True)
    match_id: Mapped[str] = mapped_column(String(32))
    team_id: Mapped[int] = mapped_column(Integer, default=0)
    team_name: Mapped[str] = mapped_column(String(128), default="")
    side: Mapped[str] = mapped_column(String(8), default="")  # home/away
    formation: Mapped[str] = mapped_column(String(16), default="")
    coach: Mapped[str] = mapped_column(String(128), default="")
    starters: Mapped[list] = mapped_column(JSON, default=list)
    subs: Mapped[list] = mapped_column(JSON, default=list)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MatchInjury(Base):
    """API-Football 伤停；同一 fixture/player/type 幂等。"""

    __tablename__ = "match_injuries"
    __table_args__ = (
        UniqueConstraint("fixture_id", "player_id", "type", name="uq_injury_fixture_player_type"),
        Index("ix_injuries_match", "match_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, index=True)
    match_id: Mapped[str] = mapped_column(String(32))
    team_id: Mapped[int] = mapped_column(Integer, default=0)
    team_name: Mapped[str] = mapped_column(String(128), default="")
    side: Mapped[str] = mapped_column(String(8), default="")
    player_id: Mapped[int] = mapped_column(Integer, default=0)
    player_name: Mapped[str] = mapped_column(String(128), default="")
    type: Mapped[str] = mapped_column(String(32), default="")
    reason: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="")
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class TeamStanding(Base):
    """API-Football 积分榜快照（联赛/赛季/球队唯一）。"""

    __tablename__ = "team_standings"
    __table_args__ = (
        UniqueConstraint("league_id", "season", "team_id", name="uq_standing_league_season_team"),
        Index("ix_standings_league_season", "league_id", "season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, default=0)
    season: Mapped[int] = mapped_column(Integer, default=0)
    team_id: Mapped[int] = mapped_column(Integer, default=0)
    team_name: Mapped[str] = mapped_column(String(128), default="")
    rank: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    form: Mapped[str] = mapped_column(String(16), default="")
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ApiFootballUsage(Base):
    """API-Football 免费档每日请求计数；按 day+endpoint 原子累加。"""

    __tablename__ = "api_football_usage"
    __table_args__ = (
        UniqueConstraint("day", "endpoint", name="uq_af_usage_day_endpoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    endpoint: Mapped[str] = mapped_column(String(64), default="")
    count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LLMUsage(Base):
    """LLM 调用账本：任务/模型/tokens/成本/延迟/降级原因；Key 永不落库。"""

    __tablename__ = "llm_usage"
    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
        Index("ix_llm_usage_task_created", "task", "created_at"),
        Index("ix_llm_usage_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    session_id: Mapped[str] = mapped_column(String(64), default="")
    task: Mapped[str] = mapped_column(String(32))
    profile: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(String(96), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_cny: Mapped[float] = mapped_column(Float, default=0.0)
    price_version: Mapped[str] = mapped_column(String(32), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    error_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LLMCache(Base):
    """LLM 响应缓存；user_private 作用域的 key 必须带用户/会话，禁止跨用户命中。"""

    __tablename__ = "llm_cache"
    __table_args__ = (
        Index("ix_llm_cache_expires", "expires_at"),
        Index("ix_llm_cache_task", "task"),
    )

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    task: Mapped[str] = mapped_column(String(32))
    profile: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(96), default="")
    prompt_ver: Mapped[str] = mapped_column(String(32), default="")
    scope: Mapped[str] = mapped_column(String(16), default="public")
    input_hash: Mapped[str] = mapped_column(String(64), default="")
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LLMBudget(Base):
    """按日/任务/profile 的原子预算；reserved + spent 不允许超过 limit。"""

    __tablename__ = "llm_budgets"
    __table_args__ = (
        UniqueConstraint("day", "task", "profile", name="uq_llm_budget_day_task_profile"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    task: Mapped[str] = mapped_column(String(32))
    profile: Mapped[str] = mapped_column(String(16))
    limit_cny: Mapped[float] = mapped_column(Float, default=0.0)
    reserved_cny: Mapped[float] = mapped_column(Float, default=0.0)
    spent_cny: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PersonaLLMModel(Base):
    """人设语气翻译模型池；key 加密存储，后台只显示是否配置。"""

    __tablename__ = "persona_llm_models"
    __table_args__ = (
        UniqueConstraint("base_url", "model", name="uq_persona_llm_base_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    base_url: Mapped[str] = mapped_column(String(256), default="")
    model: Mapped[str] = mapped_column(String(96), default="")
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_s: Mapped[int] = mapped_column(Integer, default=20)
    max_tokens: Mapped[int] = mapped_column(Integer, default=800)
    temperature: Mapped[float] = mapped_column(Float, default=0.4)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LLMProfile(Base):
    """按用途命名的 LLM 接入配置（fast=对话/轻任务，deep=发布复核/深读）。

    后台可覆盖环境变量；Key 加密存储，接口只返回是否配置。
    仅允许已知 profile 名，避免后台随意新增路由。
    """

    __tablename__ = "llm_profiles"

    name: Mapped[str] = mapped_column(String(16), primary_key=True)  # fast | deep
    provider: Mapped[str] = mapped_column(String(32), default="openai_compatible")
    base_url: Mapped[str] = mapped_column(String(256), default="")
    model: Mapped[str] = mapped_column(String(96), default="")
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    input_price_cny_per_m: Mapped[float] = mapped_column(Float, default=0.0)
    output_price_cny_per_m: Mapped[float] = mapped_column(Float, default=0.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PersonaCopyCache(Base):
    """人设翻译结果缓存：同一 source/hash/persona 只生成一次。"""

    __tablename__ = "persona_copy_cache"
    __table_args__ = (
        UniqueConstraint("source_key", "source_hash", "persona",
                         name="uq_persona_copy_source_hash_persona"),
        Index("ix_persona_copy_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(128), default="")
    source_hash: Mapped[str] = mapped_column(String(64), default="")
    persona: Mapped[str] = mapped_column(String(16), default="zhuanjia")
    text: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(96), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PersonaProfile(Base):
    """人设语气配置：只改表达，不改事实；风格 prompt 可后台编辑。"""

    __tablename__ = "persona_profiles"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), default="")
    address: Mapped[str] = mapped_column(String(16), default="")
    tone: Mapped[str] = mapped_column(String(64), default="")
    style_prompt: Mapped[str] = mapped_column(Text, default="")
    max_chars: Mapped[int] = mapped_column(Integer, default=220)
    emoji_policy: Mapped[str] = mapped_column(String(16), default="none")
    allowed_emoji: Mapped[str] = mapped_column(String(32), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PersonaCopySlot(Base):
    """前端文案槽位兜底模板（预留）；当前运行时尚未消费，回退在 narrate.py。"""

    __tablename__ = "persona_copy_slots"
    __table_args__ = (
        UniqueConstraint("persona_id", "slot_key", name="uq_persona_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[str] = mapped_column(String(16), index=True)
    slot_key: Mapped[str] = mapped_column(String(32))
    template: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class DecisionSnapshot(Base):
    """面向推荐/组合/付费/复盘的不可变决策快照。

    verdict 仍是三闸与封存事实源；snapshot 把“这次要对外表达的判断”固定成
    canonical payload，并承载发布生命周期。任何消费端只认 snapshot_id。
    """

    __tablename__ = "decision_snapshots"
    __table_args__ = (
        UniqueConstraint("trade_date", "match_id", "version",
                         name="uq_decision_snapshot_version"),
        Index("ix_decision_snapshots_trade_status", "trade_date", "status"),
        Index("ix_decision_snapshots_match_trade", "match_id", "trade_date"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)
    match_id: Mapped[str] = mapped_column(String(32), index=True)
    match_no: Mapped[str] = mapped_column(String(16), default="")
    verdict_id: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    review_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class RecommendationPlan(Base):
    """组合参谋的 canonical 快照；legs 只存 verdict_id，check 为同一套 4D 体检结果。"""

    __tablename__ = "recommendation_plans"
    __table_args__ = (
        UniqueConstraint("trade_date", "risk_profile", "version",
                         name="uq_recommendation_plan_version"),
        Index("ix_recommendation_plans_trade_status", "trade_date", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)
    risk_profile: Mapped[str] = mapped_column(String(16), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    label: Mapped[str] = mapped_column(String(32), default="")
    legs: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    review_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ReviewRun(Base):
    """AI/规则复核运行记录：每层结果、模型、prompt 版本全部留档。"""

    __tablename__ = "review_runs"
    __table_args__ = (
        Index("ix_review_runs_subject", "subject_type", "subject_id"),
        Index("ix_review_runs_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(16), index=True)
    subject_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default="failed", index=True)
    layers: Mapped[list] = mapped_column(JSON, default=list)
    reviewer: Mapped[str] = mapped_column(String(64), default="rules")
    prompt_ver: Mapped[str] = mapped_column(String(32), default="review-v1")
    llm_degraded: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RecommendationEvent(Base):
    """推荐主链审计：build/review/publish/expire/withdraw。"""

    __tablename__ = "recommendation_events"
    __table_args__ = (Index("ix_recommendation_events_subject", "subject_type", "subject_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(16), index=True)
    subject_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(24))
    from_status: Mapped[str] = mapped_column(String(24), default="")
    to_status: Mapped[str] = mapped_column(String(24), default="")
    actor: Mapped[str] = mapped_column(String(64), default="pipeline")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdminUser(Base):
    """管理后台账号：OPC 可先单账号，后续多人按角色授权。"""

    __tablename__ = "admin_users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_admin_users_username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default="operator")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AdminAudit(Base):
    """管理后台写操作审计：谁、何时、对什么、改前/改后。"""

    __tablename__ = "admin_audit"
    __table_args__ = (
        Index("ix_admin_audit_created", "created_at"),
        Index("ix_admin_audit_actor", "actor"),
        Index("ix_admin_audit_action", "action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="")
    action: Mapped[str] = mapped_column(String(32), default="")
    target_type: Mapped[str] = mapped_column(String(32), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ModelEval(Base):
    """模型评估（校准 + 回测框架产物）。"""

    __tablename__ = "model_evals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    label: Mapped[str] = mapped_column(String(64), default="")
    params: Mapped[dict] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)


class User(Base):
    """用户（自建认证：设备令牌为免登录态；W5 增补手机号/邮箱绑定 + JWT refresh）。"""

    __tablename__ = "users"
    __table_args__ = (
        # Postgres 部分唯一索引：NULL 可多行；SQLite 上退化为普通唯一索引（NULL 仍可多行）。
        Index("uq_users_phone", "phone", unique=True,
              postgresql_where=text("phone IS NOT NULL")),
        Index("uq_users_email", "email", unique=True,
              postgresql_where=text("email IS NOT NULL")),
        Index("ix_users_deleted_at", "deleted_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    device_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    persona: Mapped[str] = mapped_column(String(16), default="zhuanjia")
    discipline_on: Mapped[bool] = mapped_column(Boolean, default=True)   # 连败保护开关
    rested_until: Mapped[str] = mapped_column(String(10), default="")    # CN 日期，空=未休息
    # 合规：年龄门/未成年锁定/自排除（服务端强制，不只靠本机）
    age_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    under18_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    self_exclusion_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    self_exclusion_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    self_exclusion_reason: Mapped[str] = mapped_column(String(128), default="")
    compliance_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    odds_format: Mapped[str] = mapped_column(String(12), default="decimal")
    locale: Mapped[str] = mapped_column(String(8), default="zh")
    region: Mapped[str] = mapped_column(String(8), default="cn")   # cn / global（F18 双区域）
    # W5 认证：手机号/邮箱（登录标识）
    phone: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 注销冷静期
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Bet(Base):
    """用户记注（W6 最小切片；W5 完整买了流程在此扩展）。"""

    __tablename__ = "bets"
    __table_args__ = (
        UniqueConstraint("user_id", "verdict_id", name="uq_user_verdict_bet"),
        Index("ix_bets_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    verdict_id: Mapped[str] = mapped_column(String(40), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    sp: Mapped[float | None] = mapped_column(Float, nullable=True)  # 下注时赔率快照
    pick_dir: Mapped[str] = mapped_column(String(8), default="")  # 下注时快照
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Memory(Base):
    """用户记忆（F13：每条可见可删；冲突必问不静默覆盖）。"""

    __tablename__ = "memories"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_memory"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(256))
    source: Mapped[str] = mapped_column(String(8), default="你说过")  # 自动 / 你说过
    # v1.1 记忆五类扩展（P1）：派生记忆带分类/置信/过期；旧数据默认 preference/1.0
    category: Mapped[str] = mapped_column(String(16), default="preference")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AssistantState(Base):
    """助理 worker 游标（避免每次全表扫描 revisions）。"""

    __tablename__ = "assistant_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class WatchTarget(Base):
    """用户关注：比赛 / 球队 / 联赛（F21）。target_id 对比赛是 match_id。"""

    __tablename__ = "watch_targets"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_watch_target"),
        Index("ix_watch_targets_type_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str] = mapped_column(String(8), default="match")  # match/team/league
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    events: Mapped[list] = mapped_column(JSON, default=list)  # 事件类型白名单；空=全部
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Event(Base):
    """监控事件：一场比赛/一次修订只生成一次，再扇出给用户。"""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_pending", "fanout_at", "id"),
        Index("ix_events_type_created", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[int] = mapped_column(Integer, default=1)  # 2=P0, 1=P1, 0=digest
    match_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    team_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    data_cutoff: Mapped[str] = mapped_column(String(32), default="")
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fanout_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class Notification(Base):
    """站内信 / 推送队列；同 user+event+channel 唯一，保证幂等。"""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", "channel", name="uq_user_event_channel"),
        Index("ix_notifications_user_channel_opened", "user_id", "channel", "opened_at"),
        Index("ix_notifications_status_scheduled", "status", "scheduled_at"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    channel: Mapped[str] = mapped_column(String(8), default="inapp")  # inapp/push
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    title: Mapped[str] = mapped_column(String(128), default="")
    body: Mapped[str] = mapped_column(String(512), default="")
    deeplink: Mapped[str] = mapped_column(String(256), default="")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider_msg_id: Mapped[str] = mapped_column(String(128), default="")
    last_error: Mapped[str] = mapped_column(String(512), default="")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PushToken(Base):
    """Android JPush registration_id（MVP 只做 Android；iOS 预留 platform）。"""

    __tablename__ = "push_tokens"
    __table_args__ = (UniqueConstraint("provider", "token", name="uq_push_provider_token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    platform: Mapped[str] = mapped_column(String(8), default="android")
    provider: Mapped[str] = mapped_column(String(16), default="jpush")
    token: Mapped[str] = mapped_column(String(256))
    app_version: Mapped[str] = mapped_column(String(32), default="")
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(String(256), default="")


class NotifySettings(Base):
    """通知偏好：渠道/事件/静默/每日上限/一键暂停。"""

    __tablename__ = "notify_settings"

    user_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    channels: Mapped[list] = mapped_column(JSON, default=lambda: ["inapp", "push"])
    event_types: Mapped[list] = mapped_column(JSON, default=list)  # 空=默认全开
    quiet_start: Mapped[str] = mapped_column(String(5), default="23:30")
    quiet_end: Mapped[str] = mapped_column(String(5), default="08:00")
    daily_cap: Mapped[int] = mapped_column(Integer, default=2)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class UserEvent(Base):
    """用户行为日志：查看/点击/下注/忽略/搜索/聊天；记忆推导与推送耐受度用。"""

    __tablename__ = "user_events"
    __table_args__ = (
        Index("ix_user_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    target_id: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class InteractionEvent(Base):
    """聚焦/动作/自由提问漏斗事件；匿名只存随机 session_id。"""

    __tablename__ = "interaction_events"
    __table_args__ = (
        Index("ix_interaction_events_event_created", "event", "created_at"),
        Index("ix_interaction_events_match_created", "match_id", "created_at"),
        Index("ix_interaction_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    schema_ver: Mapped[int] = mapped_column(Integer, default=1)
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), default="")
    event: Mapped[str] = mapped_column(String(32))
    match_id: Mapped[str] = mapped_column(String(32), default="")
    verdict_id: Mapped[str] = mapped_column(String(40), default="")
    action: Mapped[str] = mapped_column(String(32), default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ShareCard(Base):
    """F20 分享卡：分享编号可验（content_hash = sha256(规范化 payload)，share_id = 编号）。"""

    __tablename__ = "share_cards"

    share_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # verdict / weekly / streak
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    verdict_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    text: Mapped[str] = mapped_column(String(512), default="")
    payload: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ModelRun(Base):
    """模型/闸门运行日志：为什么砍、为什么留，可审计（F6 gate：死因与闸门日志 100% 一致）。"""

    __tablename__ = "model_runs"
    __table_args__ = (
        Index("ix_model_runs_match_date_gate", "match_id", "run_date", "gate"),
        Index("ix_model_runs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(32), index=True)
    run_date: Mapped[str] = mapped_column(String(10), index=True)
    gate: Mapped[str] = mapped_column(String(16))  # price / market / model
    result: Mapped[str] = mapped_column(String(16))  # pass / fail / pending_data
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class AuthIdentity(Base):
    """第三方/验证码登录标识（phone/email 也落此表，便于多方式归并到同一用户）。"""

    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_uid", name="uq_identity_provider_uid"),
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(16), index=True)  # phone/email/wechat/google/apple
    provider_uid: Mapped[str] = mapped_column(String(128), index=True)
    identifier_masked: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VerificationCode(Base):
    """短信/邮箱验证码（6 位，HMAC 存储，5 分钟有效，5 次尝试，单次消费）。"""

    __tablename__ = "verification_codes"
    __table_args__ = (
        Index("ix_verification_codes_target_purpose_expires",
              "target_hash", "purpose", "expires_at"),
        Index("ix_verification_codes_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(8))                    # sms / email
    target_hash: Mapped[str] = mapped_column(String(64), index=True)   # HMAC(phone|email)
    code_hash: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(16), default="login")  # login/bind/wechat_bind
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RefreshToken(Base):
    """刷新令牌（不透明随机串，哈希入库；轮换 + 复用检测 → 撤销整个 family）。"""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
