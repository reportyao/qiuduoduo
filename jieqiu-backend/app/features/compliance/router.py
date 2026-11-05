"""合规 API：年龄门 / 未成年锁定 / 自排除 / 自评。

自排除一旦生效，服务端在 /bets 与 focus.capabilities 同时拦截；本机只是补充。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import User
from ...routers.w6 import current_user, optional_user
from . import service

router = APIRouter(tags=["compliance"])


class AgeGateBody(BaseModel):
    adult: bool
    birth_year: int | None = Field(default=None, ge=1900, le=2100)


class Under18Body(BaseModel):
    locked: bool


class ExclusionBody(BaseModel):
    days: int | None = Field(default=None, ge=1, le=3650)
    permanent: bool = False
    reason: str = Field(default="", max_length=128)


class AssessmentBody(BaseModel):
    score: int = Field(ge=0, le=27)
    answers: dict = Field(default_factory=dict)


@router.get("/compliance/state")
def compliance_state(user: User | None = Depends(optional_user)):
    return service.state(user)


@router.post("/gate/verify")
def gate_verify(body: AgeGateBody, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    try:
        result = service.verify_age(user, body.adult, body.birth_year)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return result


@router.post("/me/under18-lock")
def under18_lock(body: Under18Body, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    try:
        result = service.set_under18_lock(user, body.locked)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return result


@router.post("/compliance/self-exclusion")
def self_exclusion(body: ExclusionBody, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    try:
        result = service.set_self_exclusion(user, body.days, body.permanent, body.reason)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return result


@router.post("/compliance/self-assessment")
def self_assessment(body: AssessmentBody, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    try:
        result = service.set_assessment(user, body.score, body.answers)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return result
