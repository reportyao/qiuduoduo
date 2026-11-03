"""数据库引擎边界：Postgres 不跑启动期 DDL，连接池参数显式生效。"""
import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app import db as db_module
from app.config import Settings


def test_init_db_skips_postgres_ddl(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(db_module.engine.dialect, "name", "postgresql")
    monkeypatch.setattr(db_module.Base.metadata, "create_all",
                        lambda **kwargs: calls.append("create_all"))
    monkeypatch.setattr(db_module, "_ensure_columns", lambda: calls.append("ensure_columns"))

    db_module.init_db()

    assert calls == []  # schema 只允许 alembic upgrade 管


def test_init_db_restores_missing_index_on_legacy_sqlite(db):
    with db.bind.begin() as conn:
        conn.execute(text("DROP INDEX ix_verdicts_trade_kickoff"))

    db_module.init_db()

    with db.bind.connect() as conn:
        assert conn.execute(text(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='index' AND name='ix_verdicts_trade_kickoff'"
        )).scalar() == 1


def test_retention_rejects_nonpositive_days():
    with pytest.raises(ValidationError):
        Settings(event_retention_days=0)


def test_postgres_engine_uses_configured_queue_pool():
    eng = db_module.make_engine("postgresql+psycopg2://u:p@127.0.0.1:5432/jq")
    try:
        assert eng.pool.__class__.__name__ == "QueuePool"
        assert eng.pool.size() == 10
        assert eng.pool._max_overflow == 20
    finally:
        eng.dispose()
