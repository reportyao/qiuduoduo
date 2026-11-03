"""判决卡动作兼容端点（Feature-API-Mapping 的 POST /verdicts/{id}/react）。

产品前端当前直接用 /bets 与 /me/watch；这里保留旧契约，并把“不同意/不感兴趣”
写成 UserEvent 行为信号，绝不伪造未落库的反馈。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserEvent, Verdict, WatchTarget
from ..routers.w6 import BetBody, bet_create, current_user

router = APIRouter()


class ReactBody(BaseModel):
    action: str
    amount: float = Field(default=100.0, gt=0, le=100000)
    confirm: bool = False
    events: list[str] | None = None


class ReactResponse(BaseModel):
    action: str
    recorded: bool
    bet_id: int | None = None
    watch_id: int | None = None
    message: str


@router.post("/verdicts/{verdict_id}/react", response_model=ReactResponse)
def react(verdict_id: str, body: ReactBody, user: User = Depends(current_user),
          db: Session = Depends(get_db)):
    v = db.get(Verdict, verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    if body.action == "bet":
        out = bet_create(BetBody(verdict_id=verdict_id, amount=body.amount,
                                 confirm=body.confirm), user, db)
        return {"action": "bet", "recorded": True, "bet_id": out["id"],
                "message": "已记录注单；可在 10 秒内撤销。"}
    if body.action == "watch":
        row = db.scalar(select(WatchTarget).where(
            WatchTarget.user_id == user.id, WatchTarget.target_type == "match",
            WatchTarget.target_id == v.match_id))
        if row is None:
            row = WatchTarget(user_id=user.id, target_type="match",
                              target_id=v.match_id,
                              events=(body.events if body.events is not None else []))
            db.add(row)
        elif body.events is not None:
            row.events = body.events
        db.commit()
        db.refresh(row)
        return {"action": "watch", "recorded": True, "watch_id": row.id,
                "message": "已关注这场比赛。"}
    if body.action in ("disagree", "not_interested"):
        db.add(UserEvent(user_id=user.id, kind=f"verdict_{body.action}",
                         target_id=verdict_id,
                         metadata_json={"source": "verdict_react"}))
        db.commit()
        return {"action": body.action, "recorded": True,
                "message": "反馈已记录；不会改变封存结论或历史哈希。"}
    raise HTTPException(422, "action 必须是 bet / watch / disagree / not_interested")
