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

from sqlalchemy import delete, exists, func, select

from .config import get_settings
from .db import SessionLocal
from .models import (Event, ModelRun, Notification, RefreshToken, UserEvent,
                     VerificationCode)

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _cutoff(days: int) -> datetime:
    return NOW - timedelta(days=days)


def _count(db, model, condition) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(condition)) or 0)


def _event_condition(st):
    # 不能只按 events 自己的年龄删：notifications 保留 180 天、events 只保留 90 天，
    # 没有外键，但 event_id 仍是扇出去重键。SQLite 的 INTEGER PRIMARY KEY 在删掉
    # 最高行后会复用 ID，旧通知的 event_id 可能撞上新事件，导致新通知被判“已存在”。
    # 因此只要还有 notification 引用，就先保留 event；等通知被清掉后的下一轮再删。
    return (Event.created_at < _cutoff(st.event_retention_days)) & (
        Event.fanout_at.isnot(None) | (Event.expires_at < NOW)
    ) & ~exists(select(Notification.id).where(Notification.event_id == Event.id))


def _notification_condition(st):
    return (Notification.created_at < _cutoff(st.notification_retention_days)) & (
        Notification.status.in_(("sent", "failed", "suppressed"))
    )


def plan(db) -> dict[str, int]:
    st = get_settings()
    return {
        "events": _count(db, Event, _event_condition(st)),
        "notifications": _count(db, Notification, _notification_condition(st)),
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


def _delete_batches(db, model, condition, batch_size: int = 1000) -> int:
    """按主键分批删除，避免一次大事务长时间持锁。

    清理的是可再生日志，不要求跨表原子性；每批独立提交，失败时已完成批次保留，
    真实错误直接向上抛给运维，不静默吞掉。
    """
    total = 0
    while True:
        ids = db.scalars(
            select(model.id).where(condition).order_by(model.id).limit(batch_size)
        ).all()
        if not ids:
            break
        result = db.execute(delete(model).where(model.id.in_(ids)))
        affected = (result.rowcount
                    if result.rowcount is not None and result.rowcount >= 0
                    else len(ids))
        if affected == 0:
            # 条件选出了行但一行都没删掉：再循环会原地打转，直接暴露给运维。
            raise RuntimeError(f"retention delete made no progress on {model.__tablename__}")
        total += affected
        db.commit()
        if len(ids) < batch_size:
            break
    return total


def apply(db) -> dict[str, int]:
    st = get_settings()
    deleted: dict[str, int] = {}

    deleted["events"] = _delete_batches(db, Event, _event_condition(st))
    deleted["notifications"] = _delete_batches(db, Notification, _notification_condition(st))

    for key, model, cutoff in (
        ("model_runs", ModelRun, st.model_run_retention_days),
        ("user_events", UserEvent, st.user_event_retention_days),
        ("verification_codes", VerificationCode, st.verification_code_retention_days),
    ):
        deleted[key] = _delete_batches(db, model, model.created_at < _cutoff(cutoff))

    deleted["refresh_tokens"] = _delete_batches(
        db, RefreshToken, RefreshToken.expires_at < NOW
    )
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
