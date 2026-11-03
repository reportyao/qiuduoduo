"""助理 worker：生成事件 → 扇出 → 发推送。

用法：
  python -m app.features.assistant.worker --once
  python -m app.features.assistant.worker --loop --interval 60
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import SessionLocal
from ...models import Notification, PushToken
from .fanout import fanout_events
from .monitors import run_monitors
from .providers import PushMessage, PushResult, get_push_provider

logger = logging.getLogger("jieqiu.assistant")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def send_pending_push(db: Session, limit: int = 50, now: datetime | None = None) -> dict:
    now = now or _now()
    rows = db.scalars(select(Notification).where(
        Notification.channel == "push",
        Notification.status == "pending",
        Notification.scheduled_at <= now,
        (Notification.lease_until.is_(None) | (Notification.lease_until < now)),
    ).order_by(Notification.id).limit(limit)).all()
    sent = failed = suppressed = 0
    provider = get_push_provider("jpush")
    for n in rows:
        n.status = "sending"
        n.lease_until = now + timedelta(seconds=60)
        n.attempt = (n.attempt or 0) + 1
        db.commit()
        tokens = db.scalars(select(PushToken.token).where(
            PushToken.user_id == n.user_id, PushToken.enabled.is_(True))).all()
        if not tokens:
            n.status = "suppressed"
            n.last_error = "no_token"
            n.lease_until = None
            suppressed += 1
            db.commit()
            continue
        try:
            res = provider.send(list(tokens), PushMessage(
                title=n.title, body=n.body, deeplink=n.deeplink))
        except Exception as e:  # noqa: BLE001 provider 异常不拖垮 worker
            res = PushResult(False, error=str(e)[:300])
        if res.ok:
            n.status = "sent"
            n.sent_at = _now()
            n.provider_msg_id = res.provider_msg_id
            n.last_error = ""
            n.lease_until = None
            for t in db.scalars(select(PushToken).where(
                    PushToken.user_id == n.user_id, PushToken.enabled.is_(True))):
                t.failure_count = 0
                t.last_error = ""
            sent += 1
        else:
            n.last_error = res.error[:500]
            n.lease_until = None
            if n.attempt >= 3:
                n.status = "failed"
                failed += 1
            else:
                n.status = "pending"
                n.scheduled_at = _now() + timedelta(seconds=60 * (2 ** n.attempt))
            # 只有明确“token 无效”才累计并停用；网络/5xx 不惩罚设备
            invalid = any(x in (res.error or "").lower() for x in
                          ("invalid", "registration", "not found", "1011"))
            if invalid:
                for t in db.scalars(select(PushToken).where(
                        PushToken.user_id == n.user_id, PushToken.enabled.is_(True))):
                    t.failure_count = (t.failure_count or 0) + 1
                    t.last_error = res.error[:250]
                    if t.failure_count >= 3:
                        t.enabled = False
        db.commit()
    return {"picked": len(rows), "sent": sent, "failed": failed, "suppressed": suppressed}


def run_once(db: Session, backfill: bool = False) -> dict:
    try:
        monitors = run_monitors(db, backfill=backfill)
        fanout = fanout_events(db)
        push = send_pending_push(db)
        return {"monitors": monitors, "fanout": fanout, "push": push}
    except Exception:
        db.rollback()
        raise


def _lock():
    """防止 cron 重叠执行（Linux flock；Windows 开发环境跳过）。"""
    try:
        import fcntl
    except ImportError:
        return None
    f = open("/tmp/jieqiu-assistant.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        f.close()
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--backfill", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    lock = _lock()
    if lock is False:
        print("another assistant worker is running; skip")
        return
    db = SessionLocal()
    try:
        if args.loop:
            while True:
                try:
                    logger.info("run %s", run_once(db, backfill=args.backfill))
                except Exception:  # noqa: BLE001 worker 不退出
                    db.rollback()
                    logger.exception("assistant worker failed")
                db.expire_all()
                time.sleep(max(10, args.interval))
        else:
            print(run_once(db, backfill=args.backfill))
    finally:
        db.close()
        if lock not in (None, False):
            lock.close()


if __name__ == "__main__":
    main()
