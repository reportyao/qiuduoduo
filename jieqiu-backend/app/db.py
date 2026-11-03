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
        "phone": "TEXT",
        "email": "TEXT",
        "phone_verified": "BOOLEAN",
        "email_verified": "BOOLEAN",
        "deleted_at": "TIMESTAMP",
    },
    "memories": {
        "category": "VARCHAR(16) DEFAULT 'preference'",
        "confidence": "FLOAT DEFAULT 1.0",
        "expires_at": "TIMESTAMP",
        "last_used_at": "TIMESTAMP",
    },
}


def _existing_columns(conn, table: str) -> set[str]:
    """方言无关的列表查询：SQLite=PRAGMA，PostgreSQL=information_schema（方案 B）。"""
    from sqlalchemy import text
    dialect = engine.dialect.name
    if dialect == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {r[1] for r in rows}
    if dialect in ("postgresql", "postgres"):
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t"), {"t": table}).fetchall()
        return {r[0] for r in rows}
    return set()


def _ensure_columns() -> None:
    from sqlalchemy import text

    dialect = engine.dialect.name
    bool_false, bool_type = ("0", "BOOLEAN") if dialect == "sqlite" else ("false", "BOOLEAN")
    with engine.connect() as conn:
        for table, cols in _REQUIRED_COLUMNS.items():
            existing = _existing_columns(conn, table)
            if not existing:
                continue  # 表还不存在（create_all 刚建，一定含全部列）
            for col, typ in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        # W5 认证：布尔回填 + 手机/邮箱唯一索引（NULL 允许多行；PG/SQLite 均支持部分索引）
        try:
            conn.execute(text(f"UPDATE users SET phone_verified = {bool_false} WHERE phone_verified IS NULL"))
            conn.execute(text(f"UPDATE users SET email_verified = {bool_false} WHERE email_verified IS NULL"))
        except Exception:
            pass
        for stmt in (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone ON users(phone) WHERE phone IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users(email) WHERE email IS NOT NULL",
        ):
            try:
                conn.execute(text(stmt))
            except Exception:
                pass
        conn.commit()
