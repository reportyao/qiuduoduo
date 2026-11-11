"""公开目录/成本/日历 API：补齐 Feature-API-Mapping 中已有数据支撑的端点。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ...db import get_db
from . import service
from .schemas import (AvoidListResponse, CalendarResponse, MatchEvidenceResponse,
                      MatchListResponse, TrueCostResponse, VerdictTodayResponse)

router = APIRouter()


def _today() -> str:
    return datetime.now(service.CN).strftime("%Y-%m-%d")


def _bad_date(err: ValueError) -> HTTPException:
    return HTTPException(422, str(err))


@router.get("/matches", response_model=MatchListResponse)
def matches(date: str | None = None, status: str | None = None,
            league: str | None = None, limit: int = 100,
            db=Depends(get_db)):
    """按竞彩日列比赛（F22 分类接口），带最新判决状态/抽水/三关。"""
    if status is not None and status not in service.STATUSES:
        raise HTTPException(422, f"status 必须是 {', '.join(service.STATUSES)}")
    limit = max(1, min(limit, 200))
    d = date or _today()
    try:
        return service.list_matches(db, d, status=status, league=league, limit=limit)
    except ValueError as e:
        raise _bad_date(e)


@router.get("/verdicts/today", response_model=VerdictTodayResponse)
def verdicts_today(date: str | None = None, db=Depends(get_db)):
    """当日全部判决（含 promoted/screening/killed），用于首页之外的目录页。"""
    d = date or _today()
    try:
        return service.verdicts_today(db, d)
    except ValueError as e:
        raise _bad_date(e)


@router.get("/matches/{match_id}/cost", response_model=TrueCostResponse)
def match_cost(match_id: str, pool: str | None = None, db=Depends(get_db)):
    """真实成本：Σ(1/SP) 抽水、去水概率、公平赔率、每 100 元成本。"""
    if pool is not None and pool not in ("had", "hhad"):
        raise HTTPException(422, "pool 必须是 had / hhad")
    try:
        out = service.true_cost(db, match_id, pool=pool)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if out is None:
        raise HTTPException(404, "match or snapshot not found")
    return out


@router.get("/matches/{match_id}/evidence", response_model=MatchEvidenceResponse)
def match_evidence(match_id: str, date: str | None = None, db=Depends(get_db)):
    """比赛级判断依据：取该场最新（或指定竞彩日）判决的证据。"""
    try:
        out = service.match_evidence(db, match_id, date=date)
    except ValueError as e:
        raise _bad_date(e)
    if out is None:
        raise HTTPException(404, "match or verdict not found")
    return out


@router.get("/avoid-list", response_model=AvoidListResponse)
def avoid_list(date: str | None = None, limit: int = 50, db=Depends(get_db)):
    """避雷榜：被砍场次 + 首道死闸原因；与 stream.avoid 同口径。"""
    limit = max(1, min(limit, 100))
    d = date or service.datetime.now(service.CN).strftime("%Y-%m-%d")
    try:
        return service.avoid_list(db, d, limit=limit)
    except ValueError as e:
        raise _bad_date(e)


@router.get("/calendar", response_model=CalendarResponse)
def calendar(month: str | None = None, db=Depends(get_db)):
    """日历：按竞彩日统计场次/判决数，供日期切换与非比赛日判断。"""
    try:
        return service.calendar_month(db, month)
    except ValueError as e:
        raise _bad_date(e)
