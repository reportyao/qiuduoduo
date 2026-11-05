"""数据库引擎与会话。SQLAlchemy 2.0，SQLite 开发 / PostgreSQL 16（腾讯云，方案 B）生产同套代码。"""
import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or get_settings().database_url
    settings = get_settings()
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import NullPool
        kwargs["poolclass"] = NullPool  # 线程安全：SQLite 连接不复用跨线程（W6 深审查）
        kwargs["connect_args"] = {"check_same_thread": False}
    elif url.startswith(("postgresql", "postgres")):
        # 同步 SQLAlchemy + psycopg2：显式连接池参数，避免默认池在高并发下耗尽。
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
            connect_args={
                "application_name": "jieqiu-api",
                "options": (
                    f"-c statement_timeout={settings.db_statement_timeout_ms} "
                    f"-c lock_timeout={settings.db_lock_timeout_ms}"
                ),
            },
        )
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(eng, "connect")
        def _sqlite_pragma(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")       # cron 写 + API 读并发（W6 深审查）
            cur.execute("PRAGMA synchronous=NORMAL")     # WAL 下安全且明显减少 fsync
            cur.execute("PRAGMA busy_timeout=5000")      # 锁等待 5s，不再瞬时报 locked
            cur.execute("PRAGMA temp_store=MEMORY")
            cur.execute("PRAGMA cache_size=-20000")      # ~20MB page cache
            cur.execute("PRAGMA mmap_size=67108864")     # 64MB mmap，降低读放大
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return eng


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # 任何未处理异常都先回滚，避免连接带着失败事务回到池里。
        # 连接已断时 rollback 也可能失败，不能让清理异常覆盖原始错误。
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()


def init_db() -> None:
    """仅 SQLite/本地开发建表；Postgres 的 schema 只由 Alembic 管。

    生产启动时执行 create_all/ALTER 会绕过迁移审计，多 worker 并发启动还可能
    同时抢 DDL 锁。Postgres 部署由 deploy.py 在重启前跑 `alembic upgrade head`，
    应用启动只负责连接，不负责改 schema。
    """
    from . import models  # noqa: F401 确保模型注册

    if engine.dialect.name in ("postgresql", "postgres"):
        return
    # 旧 SQLite 库已有表时，create_all 不会补建后来新增的索引；先记下是否存在。
    from sqlalchemy import inspect
    existed = bool(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine)
    if existed:
        _ensure_columns()
        _ensure_indexes()


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
        "closing_sp_h": "FLOAT",
        "closing_sp_d": "FLOAT",
        "closing_sp_a": "FLOAT",
        "closing_at": "TIMESTAMP",
        "clv": "FLOAT",
    },
    "verdict_revisions": {
        "chain_prev": "TEXT",
        "chain_hash": "TEXT",
        "trade_date": "TEXT",
    },
    "bets": {
        "sp": "FLOAT",
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
        "age_verified": "BOOLEAN",
        "birth_year": "INTEGER",
        "under18_locked": "BOOLEAN",
        "self_exclusion_until": "TIMESTAMP",
        "self_exclusion_at": "TIMESTAMP",
        "self_exclusion_reason": "TEXT",
        "compliance_json": "JSON",
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


def _ensure_indexes() -> None:
    """给旧 SQLite 库补建模型里声明的索引。

    create_all(checkfirst=True) 只建缺失的表，不会给已存在的表补索引；生产即便
    暂时还跑 SQLite，也要让热路径索引真正生效。Postgres 不走这里，由 Alembic 管。
    """
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)


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
                # 旧库可能有重复手机/邮箱；不能静默通过，否则 auth 会绑到任意一行。
                logger.warning("legacy unique index not created: %s", stmt, exc_info=True)
        conn.commit()
