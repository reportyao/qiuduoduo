"""家宽采集器心跳与远程重启指令。

服务器无法主动连家庭机器；采集器每轮 POST 心跳，服务器在响应里下发
`restart=true`，采集器退出，由本地 watchdog/任务计划拉起。
"""
from __future__ import annotations

import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import CollectorStatus

router = APIRouter(tags=["collector"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class Heartbeat(BaseModel):
    host: str = Field(default="", max_length=128)
    pid: str = Field(default="", max_length=32)
    version: str = Field(default="", max_length=32)
    started_at: str | None = None
    last_success_at: str | None = None
    last_error: str = Field(default="", max_length=300)
    cycle: int = Field(default=0, ge=0)
    matches: int = Field(default=0, ge=0)
    snapshots_total: int = Field(default=0, ge=0)
    last_push_at: str | None = None


@router.post("/collector/heartbeat")
def collector_heartbeat(body: Heartbeat,
                        authorization: str | None = Header(default=None),
                        db: Session = Depends(get_db)):
    token = get_settings().collector_token.strip()
    if not token:
        raise HTTPException(503, "采集器心跳未启用（JQ_COLLECTOR_TOKEN 未配置）")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, token):
        raise HTTPException(401, "采集器令牌无效")

    now = _utcnow()
    row = db.get(CollectorStatus, 1)
    if row is None:
        row = CollectorStatus(id=1, last_seen=now)
        db.add(row)
    started = _parse(body.started_at)
    requested = row.restart_requested_at
    restart = False
    if requested is not None:
        if started is not None and started > requested:
            row.restart_requested_at = None
        else:
            restart = True
    row.host = body.host[:128]
    row.pid = body.pid[:32]
    row.version = body.version[:32]
    row.started_at = started
    row.last_seen = now
    row.last_success_at = _parse(body.last_success_at)
    row.last_error = body.last_error[:300]
    row.last_error_at = now if body.last_error else row.last_error_at
    row.cycle = body.cycle
    row.matches = body.matches
    row.snapshots_total = body.snapshots_total
    row.last_push_at = _parse(body.last_push_at)
    db.commit()
    return {"ok": True, "restart": restart, "server_time": now.isoformat()}
