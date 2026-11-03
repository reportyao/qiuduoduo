"""pytest 公共夹具：独立 sqlite 文件库 + FastAPI TestClient（依赖覆盖）。"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# 在导入 app 之前锁定测试库（放系统临时目录；隔离靠 drop_all/create_all，不依赖删文件）
_TEST_DB = Path(tempfile.gettempdir()) / "jq_test_jieqiu.db"
os.environ["JQ_DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["JQ_ENV"] = "test"
os.environ["JQ_XG_DATA_PATH"] = ""
os.environ["JQ_FREEZE_BASELINE"] = str(Path(tempfile.gettempdir()) / "jq_test_freeze.json")
os.environ["JQ_ENV"] = "test"  # 测试默认无模型 → 模闸 pending_data（单测用 mini xG 显式开启）

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base, engine, get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402

CN = timezone(timedelta(hours=8))

TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    engine.dispose()  # 释放上一用例的 sqlite 连接（Windows 文件锁）
    try:
        Path(os.environ["JQ_FREEZE_BASELINE"]).unlink(missing_ok=True)
    except OSError:
        pass
    Base.metadata.drop_all(bind=engine)
    init_db()  # create_all + 列迁移 + W5 唯一索引
    s = TestingSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture()
def client(db):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        engine.dispose()  # TestClient lifespan 里的连接也要释放（Windows 文件锁）


def today_cn() -> str:
    return datetime.now(CN).strftime("%Y-%m-%d")


def future_kickoff(day: str, hour: int = 21, minute: int = 55) -> str:
    """给一个比赛日 + 时间，返回 kickoff 字符串；若已过当日该时刻则用次日。"""
    d = datetime.strptime(day, "%Y-%m-%d").replace(hour=hour, minute=minute, tzinfo=CN)
    if d <= datetime.now(CN):
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d %H:%M:%S")
