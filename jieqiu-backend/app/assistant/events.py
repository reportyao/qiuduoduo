"""事件写入：去重、payload hash、可回放。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Event


def canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def emit_event(db: Session, *, type: str, dedupe_key: str, severity: int = 1,
               match_id: str | None = None, team_id: str | None = None,
               payload: dict | None = None, data_cutoff: str = "",
               expires_at: datetime | None = None) -> tuple[Event | None, bool]:
    """幂等写入。返回 (event, created)；重复 dedupe_key 返回已有事件。"""
    existing = db.scalar(select(Event).where(Event.dedupe_key == dedupe_key))
    if existing is not None:
        return existing, False
    payload = payload or {}
    ev = Event(type=type, severity=severity, match_id=match_id, team_id=team_id,
               payload=payload, payload_hash=canonical_hash(payload),
               data_cutoff=data_cutoff, dedupe_key=dedupe_key[:160],
               expires_at=expires_at)
    db.add(ev)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Event).where(Event.dedupe_key == dedupe_key))
        return existing, False
    db.refresh(ev)
    return ev, True
