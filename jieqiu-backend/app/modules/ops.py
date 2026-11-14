"""OPC 任务与异常队列。"""
from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import OpsException, OpsJob, utcnow


def job_start(db: Session, job_key: str) -> int:
    row = OpsJob(job_key=job_key, status="running", started_at=utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def job_finish(db: Session, job_id: int, status: str = "ok", error: str = "") -> None:
    row = db.get(OpsJob, job_id)
    if row is None:
        return
    row.status = status
    row.finished_at = utcnow()
    row.duration_ms = int((row.finished_at - row.started_at).total_seconds() * 1000)
    row.error = error[:300]
    db.commit()


def record_job(db: Session, job_key: str, fn):
    """执行一个 job 并记录状态；异常继续抛给调用方。"""
    job_id = job_start(db, job_key)
    started = time.time()
    try:
        result = fn()
        job_finish(db, job_id, "ok")
        return result
    except Exception as exc:
        try:
            job_finish(db, job_id, "error", f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise


def exception(db: Session, type_: str, message: str, *,
              severity: int = 1, source: str = "",
              dedupe_key: str = "", actions: list | None = None) -> OpsException | None:
    key = dedupe_key or f"{type_}:{message[:80]}"
    row = db.scalar(select(OpsException).where(OpsException.dedupe_key == key))
    if row is not None:
        if row.status == "resolved":
            row.status = "open"
            row.message = message[:400]
            row.updated_at = utcnow()
            db.commit()
        return row
    row = OpsException(type=type_, severity=severity, source=source,
                       message=message[:400], status="open",
                       actions=actions or [], dedupe_key=key[:128])
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(OpsException).where(
            OpsException.dedupe_key == key[:128]))
    return row


def list_ops(db: Session, limit: int = 50) -> dict:
    jobs = list(db.scalars(select(OpsJob).order_by(
        OpsJob.started_at.desc()).limit(limit)).all())
    summary = _job_summary(db)
    excs = list(db.scalars(select(OpsException).where(
        OpsException.status != "resolved").order_by(
        OpsException.severity.desc(), OpsException.created_at.desc()).limit(limit)).all())
    return {
        "summary": summary,
        "jobs": [{
            "id": j.id, "job_key": j.job_key, "status": j.status,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "duration_ms": j.duration_ms, "error": j.error,
        } for j in jobs],
        "exceptions": [{
            "id": e.id, "type": e.type, "severity": e.severity,
            "source": e.source, "message": e.message, "status": e.status,
            "actions": e.actions or [],
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in excs],
    }


def _job_summary(db: Session, window: int = 200) -> list[dict]:
    """按 job_key 聚合最近 window 条：运营一眼看出每个任务是否健康。"""
    rows = list(db.scalars(select(OpsJob).order_by(
        OpsJob.started_at.desc()).limit(window)).all())
    agg: dict[str, dict] = {}
    for j in rows:
        s = agg.setdefault(j.job_key, {
            "runs": 0, "errors": 0, "last_status": "",
            "last_started_at": None, "last_duration_ms": None, "last_error": "",
        })
        s["runs"] += 1
        if j.status == "error":
            s["errors"] += 1
        if s["last_started_at"] is None:
            s["last_status"] = j.status
            s["last_started_at"] = j.started_at.isoformat() if j.started_at else None
            s["last_duration_ms"] = j.duration_ms
            s["last_error"] = j.error or ""
    return [{"job_key": key, **v} for key, v in sorted(
        agg.items(), key=lambda kv: kv[1]["last_started_at"] or "", reverse=True)]


def resolve_exception(db: Session, exception_id: int, status: str = "resolved") -> bool:
    row = db.get(OpsException, exception_id)
    if row is None:
        return False
    row.status = status if status in ("open", "ack", "resolved") else "resolved"
    row.updated_at = utcnow()
    db.commit()
    return True
