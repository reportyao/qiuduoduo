"""Alembic 环境：从应用配置读取数据库 URL，并挂载全部 ORM metadata。"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401 确保全部模型注册到 metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ConfigParser 会做 % 插值；密码里含 % 时必须转义，否则 Alembic 启动即报错。
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def _connect_args() -> dict:
    """迁移连接不套 API 的 15s 语句超时，只保留锁等待上限。

    大表建索引/回填可能超过 15s；但锁等待超过 5s 应尽快失败，避免把整站写入
    卡在 ACCESS EXCLUSIVE 队列后面。SQLite 不需要这些参数。
    """
    st = get_settings()
    if not st.database_url.startswith(("postgresql", "postgres")):
        return {}
    return {
        "application_name": "jieqiu-migrate",
        "options": f"-c statement_timeout=0 -c lock_timeout={st.db_lock_timeout_ms}",
    }


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # 不用 engine_from_config：App 的 pool/statement_timeout 会干扰迁移，且
    # 迁移必须是 NullPool 的短连接。
    connectable = create_engine(
        get_settings().database_url,
        poolclass=pool.NullPool,
        connect_args=_connect_args(),
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
