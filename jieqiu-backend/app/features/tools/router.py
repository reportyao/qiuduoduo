"""串关体检 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db import get_db
from . import service
from .schemas import (ParlayCheckRequest, ParlayCheckResponse, ParlayPlanRequest,
                      ParlayPlanResponse)

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/parlay/check", response_model=ParlayCheckResponse)
def parlay_check(body: ParlayCheckRequest, db: Session = Depends(get_db)):
    """四维串关体检：成本 / 信息 / 模型 / 结构；不输出买不买建议。"""
    return service.check_parlay(db, body)


@router.post("/parlay/plan", response_model=ParlayPlanResponse)
def parlay_plan(body: ParlayPlanRequest, db: Session = Depends(get_db)):
    """帮我配：从当日有明确方向的判决生成保守/均衡/进取参考组合。"""
    return service.plan_parlay(db, body)
