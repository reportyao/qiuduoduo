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
    """当前竞彩日（05:00 前算前一日），不是日历日。"""
    now = datetime.now(CN)
    if now.hour < 5:
        now -= timedelta(days=1)
    return now.strftime("%Y-%m-%d")


def future_kickoff(day: str, hour: int = 21, minute: int = 55) -> str:
    """给一个比赛日 + 时间，返回当前竞彩窗口内的未来 kickoff。

    竞彩日窗口是「当日 00:00 ~ 次日 04:59」。00:00–04:59 属于前一日窗口，
    此时不能再返回当天 21:55（会落到窗口外），要落在今天 02:00–04:59 内。
    """
    now = datetime.now(CN)
    today = today_cn()
    if day == today and now.hour < 5:
        two = now.replace(hour=2, minute=0, second=0, microsecond=0)
        late = now.replace(hour=4, minute=50, second=0, microsecond=0)
        if now < two:
            target = two
        elif now < late:
            target = late
        else:
            target = now + timedelta(minutes=1)
        return target.strftime("%Y-%m-%d %H:%M:%S")
    d = datetime.strptime(day, "%Y-%m-%d").replace(hour=hour, minute=minute, tzinfo=CN)
    if d <= now:
        d = (d + timedelta(days=1)).replace(
            hour=2, minute=0, second=0, microsecond=0)
    return d.strftime("%Y-%m-%d %H:%M:%S")


def admin_login(client, username: str = "admin", password: str = "dev"):
    """登录并给 TestClient 装上 CSRF 头；后台写操作现在强制 CSRF。"""
    response = client.post("/admin/api/login", json={
        "username": username, "password": password})
    assert response.status_code == 200, response.text
    client.headers["x-csrf-token"] = response.json()["csrf_token"]
    return response
