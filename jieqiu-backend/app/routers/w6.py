"""W6 端点：认证、/me、连败保护、记忆（冲突必问）、注单、复盘、周报、聊天。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from ..models import Bet, User, Verdict
from ..modules import users as U
from ..features.compliance import service as compliance_service
from ..modules.chat import respond
from ..modules.postmortem import postmortem, weekly_report

router = APIRouter()


def current_user(authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    u = U.user_from_token(db, authorization)
    if u is None:
        raise HTTPException(401, "需要登录（Authorization: Bearer <device_token>）")
    if U.is_deleted(u):
        raise HTTPException(410, detail={
            "error": "account_deleted", "cooldown_days": 7,
            "message": "账号已注销（冷静期内）。同设备令牌登录（POST /auth/device）即自动撤回。"})
    return u


def optional_user(authorization: str | None = Header(default=None),
                  db: Session = Depends(get_db)) -> User | None:
    u = U.user_from_token(db, authorization)
    if u is None or U.is_deleted(u):
        return None  # 已注销 → 按匿名处理
    return u


# ---------- 请求模型 ----------

class DeviceLogin(BaseModel):
    device_token: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=8)   # cn / global（F18 双区域）


class MePatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    persona: str | None = Field(default=None, max_length=16)
    odds_format: str | None = Field(default=None, max_length=12)
    locale: str | None = Field(default=None, max_length=8)


class DisciplineBody(BaseModel):
    enabled: bool


class MemoryBody(BaseModel):
    value: str = Field(max_length=256)
    source: str = Field(default="你说过", max_length=8)
    confirm: bool = False


class MemoryCreate(MemoryBody):
    key: str = Field(min_length=1, max_length=64)


class PersonaBody(BaseModel):
    persona: str


class PersonaResponse(BaseModel):
    persona: str


class MemoryItem(BaseModel):
    key: str
    value: str
    source: str
    category: str = "preference"
    confidence: float = 1.0
    expires_at: str | None = None


class MemoryWriteResponse(BaseModel):
    key: str
    value: str
    status: str


class MemoryDeleteResponse(BaseModel):
    deleted: str


class ComfortResponse(BaseModel):
    available: bool
    kind: str
    message: str
    bet_id: int | None = None
    amount: float | None = None
    pnl: float | None = None
    next_action: str


class BetBody(BaseModel):
    verdict_id: str = Field(min_length=1, max_length=40)
    amount: float = Field(default=100.0, gt=0, le=100000,
                          description="单注金额（元）：0 < amount ≤ 100000")
    confirm: bool = False  # 连败保护触发时，加注需显式确认（尊重自主权，不静默拦截）


class ChatBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="", max_length=64)
    match_id: str = Field(default="", max_length=32)


# ---------- 认证 / 档案 ----------

@router.post("/auth/device")
def auth_device(body: DeviceLogin, db: Session = Depends(get_db)):
    from ..config import get_settings
    if get_settings().env == "prod" and not get_settings().allow_device_login:
        raise HTTPException(403, "设备免登录已关闭，请使用手机号/邮箱登录")
    region = body.region or "cn"
    if body.region is not None and body.region not in ("cn", "global"):
        raise HTTPException(422, "region 必须是 cn / global")
    user, created = U.login_device(db, body.device_token)
    if created:
        if body.display_name:
            user.display_name = body.display_name[:64]
        user.region = region
        db.commit()
    return {"user_id": user.id, "token": user.device_token, "created": created,
            "display_name": user.display_name, "region": user.region}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..modules.auth import mask_email, mask_phone
    return {
        "user_id": user.id,
        "display_name": user.display_name,
        "persona": user.persona,
        "odds_format": user.odds_format,
        "locale": user.locale,
        "region": user.region,
        "discipline_on": user.discipline_on,
        "phone": mask_phone(user.phone) if user.phone else None,
        "email": mask_email(user.email) if user.email else None,
        "streak": U.user_streak(db, user),
        "rested_until": user.rested_until,
        "compliance": compliance_service.state(user),
        "memories": _memory_items(db, user),
    }


@router.patch("/me")
def me_patch(body: MePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """用户设置：昵称 / 人设（立即生效）/ 赔率格式 / 界面语言（F15 mapping: PATCH /me）。"""
    changed = {}
    if body.display_name is not None:
        user.display_name = body.display_name[:64]
        changed["display_name"] = user.display_name
    if body.persona is not None:
        if body.persona not in ("zhuanjia", "laopao", "meng"):
            raise HTTPException(422, "persona 必须是 zhuanjia / laopao / meng")
        user.persona = body.persona
        changed["persona"] = user.persona
    if body.odds_format is not None:
        if body.odds_format not in ("decimal", "hk", "indo", "american"):
            raise HTTPException(422, "odds_format 不支持")
        user.odds_format = body.odds_format
        changed["odds_format"] = user.odds_format
    if body.locale is not None:
        if body.locale not in ("zh", "en"):
            raise HTTPException(422, "locale 支持 zh / en")
        user.locale = body.locale
        changed["locale"] = user.locale
    db.commit()
    return {"changed": changed}


@router.patch("/me/persona", response_model=PersonaResponse)
def me_persona(body: PersonaBody, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """兼容 TechSpec 的 PATCH /me/persona；与 PATCH /me 的人设字段同一逻辑。"""
    if body.persona not in ("zhuanjia", "laopao", "meng"):
        raise HTTPException(422, "persona 必须是 zhuanjia / laopao / meng")
    user.persona = body.persona
    db.commit()
    return {"persona": user.persona}


@router.delete("/me")
def me_delete(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """注销（冷静期 7 天）：打标不删数据；同令牌登录即撤回。"""
    U.soft_delete(db, user)
    return {"deleted": True, "cooldown_days": 7,
            "message": "进入 7 天冷静期。期间用原手机号登录即自动撤回注销；期满数据将被清除。"}


# ---------- F11 连败保护 / F7 休息 ----------

@router.post("/me/discipline")
@router.patch("/me/discipline")
def set_discipline(body: DisciplineBody, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    user.discipline_on = body.enabled
    db.commit()
    return {"discipline_on": user.discipline_on, "streak": U.user_streak(db, user)}


@router.post("/me/rest")
def me_rest(user: User = Depends(current_user), db: Session = Depends(get_db)):
    until = U.set_rest(db, user)
    return {"rested_until": until, "message": "好，明晚 19:02 结论照常等你。"}


@router.post("/me/unrest")
def me_unrest(user: User = Depends(current_user), db: Session = Depends(get_db)):
    U.clear_rest(db, user)
    return {"rested_until": ""}


@router.get("/me/comfort", response_model=ComfortResponse)
def me_comfort(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """买后安抚卡：按最近一注的真实状态给一句话 + 下一步，不制造“稳”的暗示。"""
    row = db.execute(
        select(Bet, Verdict).join(Verdict, Bet.verdict_id == Verdict.id)
        .where(Bet.user_id == user.id).order_by(Bet.created_at.desc()).limit(1)
    ).first()
    if row is None:
        return {"available": False, "kind": "empty",
                "message": "还没有记注。先看今天的判决，算清成本再决定。",
                "next_action": "看判决流"}
    b, v = row
    pnl = U.bet_pnl(b, v)
    if v.settled == "win":
        return {"available": True, "kind": "settled_win",
                "message": f"这注 {b.amount:.0f} 元已结算，按 SP 计盈利 {pnl:.2f} 元。"
                           "一次结果不代表长期优势，继续按成本账走。",
                "bet_id": b.id, "amount": b.amount, "pnl": pnl,
                "next_action": "看复盘"}
    if v.settled == "lose":
        return {"available": True, "kind": "settled_lose",
                "message": f"这注 {b.amount:.0f} 元已结算，亏损 {-pnl:.2f} 元。"
                           "亏损以本金为上限，别用加注把它追回来。",
                "bet_id": b.id, "amount": b.amount, "pnl": pnl,
                "next_action": "看复盘或休息"}
    return {"available": True, "kind": "pending",
            "message": f"已记录 {b.amount:.0f} 元，赛果未出。"
                       "无论结果如何，这注的最大损失就是本金。",
            "bet_id": b.id, "amount": b.amount, "pnl": None,
            "next_action": "等结算，不再加注"}



# ---------- F13 记忆 ----------

def _memory_items(db: Session, user: User) -> list[dict]:
    return [{"key": m.key, "value": m.value, "source": m.source,
             "category": getattr(m, "category", "preference"),
             "confidence": getattr(m, "confidence", 1.0),
             "expires_at": (m.expires_at.isoformat() if getattr(m, "expires_at", None)
                            else None)}
            for m in U.list_memories(db, user.id)]


@router.get("/me/memories", response_model=list[MemoryItem])
def memories_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _memory_items(db, user)


@router.get("/memories", response_model=list[MemoryItem], deprecated=True)
def memories_root(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """兼容 TechSpec 的 GET /memories（与 /me/memories 同数据）。"""
    return _memory_items(db, user)


@router.post("/memories", response_model=MemoryWriteResponse, deprecated=True)
def memory_create(body: MemoryCreate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """兼容 TechSpec 的 POST /memories：key 在 body 里。"""
    return memory_put(body.key, MemoryBody(value=body.value, source=body.source,
                                           confirm=body.confirm), user, db)


@router.put("/me/memories/{key}", response_model=MemoryWriteResponse)
def memory_put(key: str, body: MemoryBody, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    if not key.strip():
        raise HTTPException(422, "key 不能为空")
    if "/" in key:
        raise HTTPException(422, "key 不能包含 /")
    m, status = U.upsert_memory(db, user.id, key, body.value, body.source, body.confirm)
    if status == "conflict":
        existing = U.list_memories(db, user.id)
        old = next((x.value for x in existing if x.key == key.strip()[:64]), "")
        raise HTTPException(409, detail={
            "error": "conflict", "key": key, "existing": old, "incoming": body.value,
            "message": "已有一条不同的记忆——确认覆盖请带 confirm=true。绝不静默覆盖。"})
    return {"key": m.key, "value": m.value, "status": status}


@router.delete("/me/memories/{key}")
def memory_delete(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not U.delete_memory(db, user.id, key):
        raise HTTPException(404, "memory not found")
    return {"deleted": key}


@router.delete("/memories/{key}", response_model=MemoryDeleteResponse, deprecated=True)
def memory_delete_root(key: str, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """兼容 TechSpec 的 DELETE /memories/{key}。"""
    return memory_delete(key, user, db)


# ---------- 注单（F11 行为面：保护期加注需确认） ----------

@router.post("/bets")
def bet_create(body: BetBody, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    v = db.get(Verdict, body.verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    if v.status != "promoted":
        raise HTTPException(422, "只能记已晋升（三关全过）的判决——这是产品纪律")
    if v.settled is not None:
        raise HTTPException(422, "这场已经结算，不能补记")
    if v.kickoff <= datetime.now(U.CN).strftime("%Y-%m-%d %H:%M:%S"):
        raise HTTPException(422, "这场已经停售，不能补记")
    block = compliance_service.bet_block_reason(user)
    if block == "under18":
        raise HTTPException(403, detail={
            "error": "under18", "message": "未满 18 周岁只能查看公开账本，不能记注。"})
    if block == "self_excluded":
        raise HTTPException(423, detail={
            "error": "self_excluded", "message": "自排除生效中，到期前不能记注。"})
    if block == "rested":
        raise HTTPException(423, detail={
            "error": "rested", "message": "你已选择今晚休息；结论照常更新，但先不记注。"})
    # F11 行为面：连败保护触发时，加注前必须显式确认（先于重复检查——保护优先提醒）
    st = U.user_streak(db, user)
    if st["active"] and not body.confirm:
        raise HTTPException(423, detail={
            "error": "protection_active", "streak": st["streak"],
            "message": f"你已连败 {st['streak']} 场，连败保护已触发。"
                       f"低谷加注是亏损扩大的最常见方式——确认继续请带 confirm=true，"
                       f"或先休息（POST /me/rest）。"})
    if db.scalar(select(Bet).where(Bet.user_id == user.id, Bet.verdict_id == v.id)):
        raise HTTPException(409, "该判决已记过注")
    b = Bet(user_id=user.id, verdict_id=v.id, amount=body.amount,
            sp=(v.pick or {}).get("sp"), pick_dir=(v.pick or {}).get("dir", ""))
    db.add(b)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "该判决已记过注")
    return {"id": b.id, "verdict_id": v.id, "amount": b.amount,
            "pick_dir": b.pick_dir, "streak": U.user_streak(db, user)}


@router.delete("/bets/{bet_id}")
def bet_delete(bet_id: int = Path(..., ge=1, le=2**63 - 1),
               user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """撤销记注（前端 5 秒撤销窗口）。只能删自己的注单，已结算的注单不允许删。"""
    b = db.get(Bet, bet_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "bet not found")
    v = db.get(Verdict, b.verdict_id)
    if v is not None and v.settled:
        raise HTTPException(409, "已结算的注单不能撤销")
    if v is not None and v.kickoff <= datetime.now(U.CN).strftime("%Y-%m-%d %H:%M:%S"):
        raise HTTPException(409, "已停售的注单不能撤销")
    # 服务端也保留撤销窗口（前端 5 秒，服务端放宽到 10 秒容时钟误差）。
    if b.created_at and (datetime.now(timezone.utc).replace(tzinfo=None) - b.created_at).total_seconds() > 10:
        raise HTTPException(409, "撤销窗口已过")
    db.delete(b)
    db.commit()
    return {"deleted": bet_id}


@router.get("/bets")
def bets_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Bet, Verdict).join(Verdict, Bet.verdict_id == Verdict.id)
        .where(Bet.user_id == user.id).order_by(Verdict.kickoff)
    ).all()
    return [{
        "id": b.id,
        "verdict_id": b.verdict_id, "match": f"{v.home} vs {v.away}",
        "match_no": v.match_no, "amount": b.amount, "pick_dir": b.pick_dir,
        "pool": v.pool, "goal_line": v.goal_line, "sp": b.sp or (v.pick or {}).get("sp"),
        "status": v.status, "settled": v.settled, "result_score": v.result_score,
        "pnl": U.bet_pnl(b, v),
    } for b, v in rows]


@router.get("/bets/{bet_id}/postmortem")
def bet_postmortem(bet_id: int = Path(..., ge=1, le=2**63 - 1),
                   user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    """注单死因回访（mapping v1.0）：死在哪关/归因 + what-if（含金额）。"""
    b = db.get(Bet, bet_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "bet not found")
    v = db.get(Verdict, b.verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    pm = postmortem(v)
    pm["bet"] = {"amount": b.amount, "pick_dir": b.pick_dir,
                 "sp": b.sp or (v.pick or {}).get("sp"),
                 "pnl": U.bet_pnl(b, v)}
    if v.settled == "lose":
        pm["whatif"] = f"若未下这注 {b.amount:.0f} 元，账户将少亏 {b.amount:.0f} 元。" \
                       "（诚实口径：赢的那几注同样真实存在，见周报。）"
    return pm


# ---------- 复盘 / 周报 / 聊天 ----------

@router.get("/verdicts/{verdict_id}/postmortem")
def verdict_postmortem(verdict_id: str, db: Session = Depends(get_db)):
    v = db.get(Verdict, verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    return postmortem(v)


@router.get("/weekly-report")
def weekly(authorization: str | None = Header(default=None),
           db: Session = Depends(get_db)):
    u = U.user_from_token(db, authorization)
    if u is not None and U.is_deleted(u):
        raise HTTPException(410, detail={
            "error": "account_deleted", "cooldown_days": 7,
            "message": "账号已注销（冷静期内）。同设备令牌登录即自动撤回。"})
    return weekly_report(db, u.id if u else None)


@router.post("/chat")
def chat(body: ChatBody, user: User | None = Depends(optional_user),
         db: Session = Depends(get_db)):
    return respond(db, user, body.text, session_id=body.session_id,
                   match_id=body.match_id)
