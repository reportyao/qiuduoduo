"""ORM 模型 · W2 核心表（对应 TechSpec §5：sp_matches / sp_snapshots / team_aliases / matches / verdicts / model_runs）。

设计约定：
- 竞彩相关时间一律存中国标准时间的 ISO 字符串（源数据即如此），不做时区换算存储。
- verdicts.payload 为规范化 JSON（sort_keys），payload_hash = sha256(canonical payload)，
  任何人可独立复算验证 —— 这是产品主张（TechSpec §3 封存纪律）。
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    __table_args__ = (UniqueConstraint("verdict_id", "payload_hash", name="uq_revision"),)

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

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    device_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    persona: Mapped[str] = mapped_column(String(16), default="zhuanjia")
    discipline_on: Mapped[bool] = mapped_column(Boolean, default=True)   # 连败保护开关
    rested_until: Mapped[str] = mapped_column(String(10), default="")    # CN 日期，空=未休息
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
    __table_args__ = (UniqueConstraint("user_id", "verdict_id", name="uq_user_verdict_bet"),)

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
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id", name="uq_watch_target"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str] = mapped_column(String(8), default="match")  # match/team/league
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    events: Mapped[list] = mapped_column(JSON, default=list)  # 事件类型白名单；空=全部
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Event(Base):
    """监控事件：一场比赛/一次修订只生成一次，再扇出给用户。"""

    __tablename__ = "events"

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
    __table_args__ = (UniqueConstraint("user_id", "event_id", "channel", name="uq_user_event_channel"),)

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    target_id: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
