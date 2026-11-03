"""数据库保留策略与轻量运维 CLI。

默认 dry-run，只打印将删除的行数；加 --apply 才执行删除。
设计原则：
- 只删“可再生的运行日志/已送达通知/过期验证码/过期 refresh token”；
- 判决、修订、锚点、注单、分享卡、SP 快照永不自动删除（产品承诺/审计需要）；
- 大批量删除应在低峰执行，生产建议先备份并用 pg_stat_activity 观察锁等待。

用法：
    python -m app.db_maint                 # dry-run
    python -m app.db_maint --apply         # 执行
    python -m app.db_maint --apply --json  # 给 cron/监控消费
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from .config import get_settings
from .db import SessionLocal
from .models import (Event, ModelRun, Notification, RefreshToken, UserEvent,
                     VerificationCode)

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _cutoff(days: int) -> datetime:
    return NOW - timedelta(days=days)


def _count(db, model, condition) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(condition)) or 0)


def plan(db) -> dict[str, int]:
    st = get_settings()
    return {
        "events": _count(
            db, Event,
            (Event.created_at < _cutoff(st.event_retention_days))
            & Event.fanout_at.isnot(None),
        ),
        "notifications": _count(
            db, Notification,
            (Notification.created_at < _cutoff(st.notification_retention_days))
            & Notification.status.in_(("sent", "failed", "skipped")),
        ),
        "model_runs": _count(
            db, ModelRun,
            ModelRun.created_at < _cutoff(st.model_run_retention_days),
        ),
        "user_events": _count(
            db, UserEvent,
            UserEvent.created_at < _cutoff(st.user_event_retention_days),
        ),
        "verification_codes": _count(
            db, VerificationCode,
            VerificationCode.created_at < _cutoff(st.verification_code_retention_days),
        ),
        "refresh_tokens": _count(
            db, RefreshToken,
            RefreshToken.expires_at < NOW,
        ),
    }


def apply(db) -> dict[str, int]:
    st = get_settings()
    deleted: dict[str, int] = {}

    result = db.execute(delete(Event).where(
        (Event.created_at < _cutoff(st.event_retention_days))
        & Event.fanout_at.isnot(None)))
    deleted["events"] = result.rowcount or 0

    result = db.execute(delete(Notification).where(
        (Notification.created_at < _cutoff(st.notification_retention_days))
        & Notification.status.in_(("sent", "failed", "skipped"))))
    deleted["notifications"] = result.rowcount or 0

    for key, model, cutoff in (
        ("model_runs", ModelRun, st.model_run_retention_days),
        ("user_events", UserEvent, st.user_event_retention_days),
        ("verification_codes", VerificationCode, st.verification_code_retention_days),
    ):
        result = db.execute(delete(model).where(model.created_at < _cutoff(cutoff)))
        deleted[key] = result.rowcount or 0

    result = db.execute(delete(RefreshToken).where(RefreshToken.expires_at < NOW))
    deleted["refresh_tokens"] = result.rowcount or 0
    db.commit()
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(description="jieqiu DB retention")
    parser.add_argument("--apply", action="store_true", help="真正删除；默认 dry-run")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        counts = apply(db) if args.apply else plan(db)
    finally:
        db.close()
    payload = {"mode": "apply" if args.apply else "dry-run", **counts}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else payload)


if __name__ == "__main__":
    main()
