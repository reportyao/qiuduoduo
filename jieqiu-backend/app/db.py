"""数据库引擎与会话。SQLAlchemy 2.0，SQLite 开发 / PostgreSQL 16（腾讯云，方案 B）生产同套代码。"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or get_settings().database_url
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import NullPool
        kwargs["poolclass"] = NullPool  # 线程安全：SQLite 连接不复用跨线程（W6 深审查）
        kwargs["connect_args"] = {"check_same_thread": False}
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(eng, "connect")
        def _sqlite_pragma(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")       # cron 写 + API 读并发（W6 深审查）
            cur.execute("PRAGMA busy_timeout=5000")      # 锁等待 5s，不再瞬时报 locked
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return eng


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401 确保模型注册

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


# 轻量列迁移：create_all 不给已有表加列，这里按需 ALTER（W2→W3 verdicts 扩展）
_REQUIRED_COLUMNS = {
    "verdicts": {
        "model_h": "FLOAT",
        "model_d": "FLOAT",
        "model_a": "FLOAT",
        "pick": "JSON",
        "rake_threshold": "FLOAT",
        "settled": "TEXT",
        "settled_at": "TIMESTAMP",
        "result_score": "TEXT",
    },
    "verdict_revisions": {
        "chain_prev": "TEXT",
        "chain_hash": "TEXT",
        "trade_date": "TEXT",
    },
    "users": {
        "odds_format": "TEXT",
        "locale": "TEXT",
        "region": "TEXT",
        "deleted_at": "TIMESTAMP",
    },
}


def _ensure_columns() -> None:
    from sqlalchemy import text

    with engine.connect() as conn:
        for table, cols in _REQUIRED_COLUMNS.items():
            try:
                rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            except Exception:
                continue  # 表还不存在（create_all 刚建，一定含全部列）
            if not rows:
                continue
            existing = {r[1] for r in rows}
            for col, typ in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        conn.commit()
