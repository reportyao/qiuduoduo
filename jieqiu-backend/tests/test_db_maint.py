"""数据库保留策略：dry-run 不动数据，apply 只删运行日志/过期令牌。"""
from datetime import datetime, timedelta, timezone

from app.models import (Event, ModelRun, Notification, RefreshToken, UserEvent,
                        VerificationCode)
from app import db_maint


NOW = datetime.now(timezone.utc).replace(tzinfo=None)
OLD = NOW - timedelta(days=400)


def test_retention_dry_run_then_apply(db, monkeypatch):
    db.add(Event(type="close_soon", dedupe_key="old-event", payload={},
                 created_at=OLD, fanout_at=OLD))
    db.add(Notification(user_id="u1", event_id=1, channel="inapp",
                        status="sent", created_at=OLD, scheduled_at=OLD))
    db.add(Notification(user_id="u1", event_id=2, channel="inapp",
                        status="pending", created_at=OLD, scheduled_at=OLD))
    db.add(ModelRun(match_id="m1", run_date="2020-01-01", gate="price",
                    result="pass", created_at=OLD))
    db.add(UserEvent(user_id="u1", kind="view", created_at=OLD))
    db.add(VerificationCode(channel="sms", target_hash="h", code_hash="c",
                            expires_at=OLD, created_at=OLD))
    db.add(RefreshToken(user_id="u1", token_hash="old-refresh", family_id="f",
                        expires_at=OLD, created_at=OLD))
    db.commit()

    plan = db_maint.plan(db)
    assert plan["events"] == 1
    assert plan["notifications"] == 1  # pending 不删
    assert plan["refresh_tokens"] == 1

    deleted = db_maint.apply(db)
    assert deleted["events"] == 1
    assert deleted["notifications"] == 1
    assert db.query(Notification).filter_by(status="pending").count() == 1
    assert db.query(RefreshToken).count() == 0
