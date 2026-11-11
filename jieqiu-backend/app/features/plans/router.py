"""计划 API：历史摘要公开，当前期完整注单仅 Max。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import PlanCycle, User
from ...modules import membership, plan_service
from ...modules.users import is_deleted, user_from_token

router = APIRouter(tags=["plans"])


def _user(authorization: str | None = Header(default=None),
          db: Session = Depends(get_db)) -> User | None:
    user = user_from_token(db, authorization)
    return None if user is None or is_deleted(user) else user


def _risk(value: str) -> str:
    if value not in plan_service.RISK_ORDER:
        raise HTTPException(422, "risk 必须是 stable/balanced/aggressive")
    return value


@router.get("/plans/summary")
def plans_summary(db: Session = Depends(get_db)):
    return {"plans": plan_service.summary(db)}


@router.get("/plans/current")
def plan_current(risk: str = Query("stable"),
                 user: User | None = Depends(_user),
                 db: Session = Depends(get_db)):
    risk = _risk(risk)
    tier = membership.tier_for(db, user.id if user else None)
    include = tier == "max"
    data = plan_service.current(db, risk, include_legs=include)
    return {"tier": tier, "locked": not include, "plan": data}


@router.get("/plans/history")
def plan_history(risk: str = Query("stable"), limit: int = Query(30, ge=1, le=100),
                 user: User | None = Depends(_user),
                 db: Session = Depends(get_db)):
    risk = _risk(risk)
    tier = membership.tier_for(db, user.id if user else None)
    include = tier == "max"
    return {"tier": tier, "locked": not include,
            "items": plan_service.history(db, risk, limit=limit, include_legs=include)}


@router.get("/plans/cycles/{cycle_id}")
def plan_cycle(cycle_id: str, user: User | None = Depends(_user),
               db: Session = Depends(get_db)):
    cycle = db.get(PlanCycle, cycle_id)
    if cycle is None or cycle.status not in ("published", "settled"):
        raise HTTPException(404, "plan cycle not found")
    tier = membership.tier_for(db, user.id if user else None)
    include = tier == "max"
    return {"tier": tier, "locked": not include,
            "plan": plan_service.cycle_detail(db, cycle, include_legs=include)}
