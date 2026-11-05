"""公开推荐读取：只返回 published 且未过期的 snapshot/plan。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import DecisionSnapshot, RecommendationPlan
from . import service
from .schemas import PlanPublic, RecommendationToday, SnapshotPublic

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/today", response_model=RecommendationToday)
def recommendations_today(date: str | None = None, db: Session = Depends(get_db)):
    return service.today(db, date)


@router.get("/{snapshot_id}", response_model=SnapshotPublic)
def recommendation_detail(snapshot_id: str, db: Session = Depends(get_db)):
    service.expire_due(db)
    row = db.get(DecisionSnapshot, snapshot_id)
    if row is None or row.status != service.PUBLISHED:
        raise HTTPException(404, "recommendation not found")
    return service._public_snapshot(db, row)


@router.get("/plans/{plan_id}", response_model=PlanPublic)
def recommendation_plan_detail(plan_id: str, db: Session = Depends(get_db)):
    service.expire_due(db)
    row = db.get(RecommendationPlan, plan_id)
    if row is None or row.status != service.PUBLISHED:
        raise HTTPException(404, "recommendation plan not found")
    return service._public_plan(db, row)
