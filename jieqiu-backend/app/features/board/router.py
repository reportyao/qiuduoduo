from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import User
from ...routers.w6 import optional_user
from . import service
from .schemas import (LiveBoardResponse, PerformanceResponse,
                      PredictionHistoryDetailResponse,
                      PredictionHistoryResponse, ResultBoardResponse)

router = APIRouter(tags=["match-board"])


@router.get("/matches/live", response_model=LiveBoardResponse)
def matches_live(date: str | None = None, force: bool = False,
                 db: Session = Depends(get_db)):
    """即时比赛：只返回有竞彩映射的进行中场次，不含预测。"""
    try:
        return service.build_live_board(db, date, force=force)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/matches/results", response_model=ResultBoardResponse)
def matches_results(date: str | None = None,
                    user: User | None = Depends(optional_user),
                    db: Session = Depends(get_db)):
    """赛果：只返回比分与状态，不展示预测。"""
    try:
        return service.build_result_board(db, date, user=user)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/predictions/history", response_model=PredictionHistoryResponse)
def prediction_history(date: str | None = None,
                       user: User | None = Depends(optional_user),
                       db: Session = Depends(get_db)):
    """预测战绩列表：汇总命中率与每场主预测，不携带 25 维明细。"""
    try:
        return service.build_prediction_history(db, date, user=user)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/predictions/performance", response_model=PerformanceResponse)
def predictions_performance(days: int = 30, db: Session = Depends(get_db)):
    """战绩看板：趋势 / 按市场 / 按联赛 / 校准，纯聚合。"""
    try:
        return service.build_performance(db, days=days)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/predictions/history/{match_id}",
            response_model=PredictionHistoryDetailResponse)
def prediction_history_detail(match_id: str, db: Session = Depends(get_db)):
    """单场全部预测维度与实际结果对照。"""
    payload = service.build_prediction_history_detail(db, match_id)
    if payload is None:
        raise HTTPException(404, "match not found")
    return payload
