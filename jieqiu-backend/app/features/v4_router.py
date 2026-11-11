"""HeaderMetrics / 每日战绩 / 会员权益只读 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..modules import engine, membership, memory_profile, performance
from ..modules.users import is_deleted, user_from_token

router = APIRouter(tags=["v4-read"])


def _user(authorization: str | None = Header(default=None),
          db: Session = Depends(get_db)) -> User | None:
    user = user_from_token(db, authorization)
    return None if user is None or is_deleted(user) else user


@router.get("/stats/engine")
def stats_engine(include_points: bool = True,
                 user: User | None = Depends(_user),
                 db: Session = Depends(get_db)):
    return engine.status(db, user, include_points=include_points)


@router.get("/stats/record/summary")
def stats_record_summary(days: int = Query(30, ge=1, le=180),
                         db: Session = Depends(get_db)):
    return {"record": performance.record_summary(db, days=days)}


@router.get("/membership/me")
def membership_me(user: User | None = Depends(_user),
                  db: Session = Depends(get_db)):
    data = membership.membership_payload(db, user.id if user else None)
    if user is not None:
        from ..modules.timeutil import trade_date_now
        data["quota"] = membership.quota_state(
            db, user.id, trade_date_now(), data["tier"])
    return data


@router.get("/me/profile")
def my_profile(user: User | None = Depends(_user),
               db: Session = Depends(get_db)):
    if user is None:
        return {"features": []}
    return {"features": memory_profile.context(db, user.id)}


@router.get("/membership/markets")
def membership_markets(user: User | None = Depends(_user),
                       db: Session = Depends(get_db)):
    tier = membership.tier_for(db, user.id if user else None)
    return {"tier": tier,
            "markets": sorted(membership.DEFAULT_MARKETS.get(tier, set()))}
