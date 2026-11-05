"""公开人设配置：前端启动时拉取，失败可用 bundled fallback。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...db import get_db
from ...modules import persona_registry
from .schemas import PersonaConfigResponse

router = APIRouter(tags=["persona"])


@router.get("/personas", response_model=PersonaConfigResponse)
def personas(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=300"
    return persona_registry.public_payload(db)
