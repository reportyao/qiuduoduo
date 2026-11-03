"""W6 端点：认证、/me、连败保护、记忆（冲突必问）、注单、复盘、周报、聊天。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bet, User, Verdict
from ..modules import users as U
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
    device_token: str | None = None
    display_name: str | None = None
    region: str | None = None   # cn / global（F18 双区域）


class MePatch(BaseModel):
    display_name: str | None = None
    persona: str | None = None
    odds_format: str | None = None
    locale: str | None = None


class DisciplineBody(BaseModel):
    enabled: bool


class MemoryBody(BaseModel):
    value: str
    source: str = "你说过"
    confirm: bool = False


class BetBody(BaseModel):
    verdict_id: str
    amount: float = Field(default=100.0, gt=0, le=100000,
                          description="单注金额（元）：0 < amount ≤ 100000")
    confirm: bool = False  # 连败保护触发时，加注需显式确认（尊重自主权，不静默拦截）


class ChatBody(BaseModel):
    text: str


# ---------- 认证 / 档案 ----------

@router.post("/auth/device")
def auth_device(body: DeviceLogin, db: Session = Depends(get_db)):
    user, created = U.login_device(db, body.device_token)
    if created:
        if body.display_name:
            user.display_name = body.display_name[:64]
        region = body.region or "cn"
        if body.region is not None:
            if body.region not in ("cn", "global"):
                raise HTTPException(422, "region 必须是 cn / global")
            region = body.region
        user.region = region
        db.commit()
    return {"user_id": user.id, "token": user.device_token, "created": created,
            "display_name": user.display_name, "region": user.region}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {
        "user_id": user.id,
        "display_name": user.display_name,
        "persona": user.persona,
        "streak": U.user_streak(db, user),
        "rested_until": user.rested_until,
        "memories": [{"key": m.key, "value": m.value, "source": m.source}
                     for m in U.list_memories(db, user.id)],
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


@router.delete("/me")
def me_delete(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """注销（冷静期 7 天）：打标不删数据；同令牌登录即撤回。"""
    U.soft_delete(db, user)
    return {"deleted": True, "cooldown_days": 7,
            "message": "进入 7 天冷静期。期间用同一设备令牌登录即自动撤回注销；期满数据将被清除。"}


# ---------- F11 连败保护 / F7 休息 ----------

@router.post("/me/discipline")
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


# ---------- F13 记忆 ----------

@router.get("/me/memories")
def memories_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"key": m.key, "value": m.value, "source": m.source}
            for m in U.list_memories(db, user.id)]


@router.put("/me/memories/{key}")
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


# ---------- 注单（F11 行为面：保护期加注需确认） ----------

@router.post("/bets")
def bet_create(body: BetBody, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    v = db.get(Verdict, body.verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    if v.status != "promoted":
        raise HTTPException(422, "只能记已晋升（三关全过）的判决——这是产品纪律")
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
            pick_dir=(v.pick or {}).get("dir", ""))
    db.add(b)
    db.commit()
    return {"id": b.id, "verdict_id": v.id, "amount": b.amount,
            "pick_dir": b.pick_dir, "streak": U.user_streak(db, user)}


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
        "status": v.status, "settled": v.settled, "result_score": v.result_score,
        "pnl": (b.amount if v.settled == "win" else -b.amount) if v.settled else None,
    } for b, v in rows]


@router.get("/bets/{bet_id}/postmortem")
def bet_postmortem(bet_id: int, user: User = Depends(current_user),
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
                 "pnl": (b.amount if v.settled == "win" else -b.amount) if v.settled else None}
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
    return weekly_report(db, u.id if u else None)


@router.post("/chat")
def chat(body: ChatBody, user: User | None = Depends(optional_user),
         db: Session = Depends(get_db)):
    return respond(db, user, body.text)
