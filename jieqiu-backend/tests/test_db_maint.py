"""数据库保留策略：dry-run 不动数据，apply 只删运行日志/过期令牌。"""
from datetime import datetime, timedelta, timezone

from app.models import (Event, ModelRun, Notification, RefreshToken, UserEvent,
                        VerificationCode)
from app import db_maint


NOW = datetime.now(timezone.utc).replace(tzinfo=None)
OLD = NOW - timedelta(days=400)


def test_retention_dry_run_then_apply(db, monkeypatch):
    e1 = Event(type="close_soon", dedupe_key="old-event", payload={},
               created_at=OLD, fanout_at=OLD)
    # 未扇出但已过期的事件也应回收；无条件保留会永久堆积
    e2 = Event(type="close_soon", dedupe_key="old-expired-event", payload={},
               created_at=OLD, fanout_at=None, expires_at=OLD)
    # 仍被通知引用的事件先保留：event_id 是扇出去重键，删早了会在 SQLite
    # 主键复用后误判新事件“已通知”。
    e3 = Event(type="close_soon", dedupe_key="referenced-event", payload={},
               created_at=OLD, fanout_at=OLD)
    db.add_all([e1, e2, e3])
    db.flush()
    db.add(Notification(user_id="u1", event_id=e3.id, channel="inapp",
                        status="sent", created_at=OLD, scheduled_at=OLD))
    db.add(Notification(user_id="u1", event_id=999998, channel="inapp",
                        status="pending", created_at=OLD, scheduled_at=OLD))
    db.add(Notification(user_id="u1", event_id=999999, channel="push",
                        status="suppressed", created_at=OLD, scheduled_at=OLD))
    db.add(ModelRun(match_id="m1", run_date="2020-01-01", gate="price",
                    result="pass", created_at=OLD))
    db.add(UserEvent(user_id="u1", kind="view", created_at=OLD))
    db.add(VerificationCode(channel="sms", target_hash="h", code_hash="c",
                            expires_at=OLD, created_at=OLD))
    db.add(RefreshToken(user_id="u1", token_hash="old-refresh", family_id="f",
                        expires_at=OLD, created_at=OLD))
    db.commit()

    plan = db_maint.plan(db)
    assert plan["events"] == 2
    assert plan["notifications"] == 2  # pending 不删；suppressed 删
    assert plan["refresh_tokens"] == 1

    deleted = db_maint.apply(db)
    assert deleted["events"] == 2
    assert deleted["notifications"] == 2
    assert db.query(Event).filter_by(id=e3.id).count() == 1  # 仍被引用，保留
    assert db.query(Notification).filter_by(status="pending").count() == 1
    assert db.query(RefreshToken).count() == 0

    # 通知清掉后的下一轮才回收该事件，避免 event_id 复用污染去重。
    second = db_maint.apply(db)
    assert second["events"] == 1
    assert db.query(Event).filter_by(id=e3.id).count() == 0
