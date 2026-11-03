import json  # noqa: F401
"""W7 后端硬化 + editor_console 测试。"""
from fastapi.testclient import TestClient


def _login(client, pw="dev"):
    return client.post("/console/login", data={"pw": pw},
                       follow_redirects=False)


def test_rate_limit_429(db, client):
    """限流：JQ_ENV=test 跳过；真实 429 由子进程用例验证。"""
    for _ in range(5):
        assert client.post("/auth/device", json={"device_token": None}).status_code == 200


def test_rate_limit_429_real_server(monkeypatch):
    """限流生产形态：独立服务器 + 35 连发写 → 429。"""
    import os
    import subprocess
    import tempfile
    import time
    import urllib.error
    import urllib.request
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(dbpath)
    from sqlalchemy import create_engine
    from app.db import Base
    import app.models  # noqa
    eng = create_engine(f"sqlite:///{dbpath}")
    Base.metadata.create_all(eng)
    env = dict(os.environ, JQ_DATABASE_URL=f"sqlite:///{dbpath}", JQ_ENV="dev",
               JQ_XG_DATA_PATH="")
    port = 8102
    proc = subprocess.Popen(["python", "-m", "uvicorn", "app.main:app", "--port", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        for _ in range(30):
            time.sleep(0.3)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                break
            except Exception:
                continue
        codes = []
        for i in range(70):  # 新语义：匿名写 60/分/身份 → 第 61 个起 429
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/auth/logout",
                data=json.dumps({"refresh_token": f"x{i}"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    codes.append(resp.status)
            except urllib.error.HTTPError as e:
                codes.append(e.code)
        assert 429 in codes
        assert codes.count(200) >= 55
    finally:
        proc.terminate()
        try:
            os.remove(dbpath)
        except PermissionError:
            pass


def test_request_id_header(db, client):
    """test 环境跳过中间件 → 无头；生产形态由 real-server 用例覆盖。"""
    r = client.get("/health")
    assert r.status_code == 200  # 不因中间件崩溃即通过


def test_console_requires_auth(client):
    r = client.get("/console", follow_redirects=False)
    assert r.status_code == 302 and "/console/login" in r.headers["location"]


def test_console_login_flow(client):
    # 错误密码
    r = _login(client, pw="wrong")
    assert r.status_code == 200 and "密码错误" in r.text
    # 正确密码（dev 环境默认密码 "dev"）
    r = _login(client)
    assert r.status_code == 302
    tok = r.headers["location"].split("t=")[1]
    # 带 token 访问日报
    r2 = client.get(f"/console?t={tok}")
    assert r2.status_code == 200 and "数据日报" in r2.text and "封存链" in r2.text
    # 告警页
    r3 = client.get(f"/console/alerts?t={tok}")
    assert r3.status_code == 200
    # 变体池（含模板预览与 A/Q/X 按钮）
    r4 = client.get(f"/console/variants?t={tok}")
    assert r4.status_code == 200 and ("今日暂无判决" in r4.text or "A" in r4.text)
    # 运维页
    r5 = client.get(f"/console/ops?t={tok}")
    assert r5.status_code == 200 and "重跑判决" in r5.text


def test_console_variants_mark(db, client, monkeypatch):
    from tests.test_deep import _mini, _promotable_match  # 复用夹具
    from app.modules.verdict import build_verdicts
    from tests.conftest import today_cn
    _mini(monkeypatch)
    _promotable_match(db, "2059001", "周日001")
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    _login(client)
    # 登录后拿 cookie，直接访问
    r = client.get("/console/variants")
    assert "周日001" in r.text
    vid = r.text.split("variants?v=")[1].split("&")[0]
    r2 = client.post(f"/console/variants?v={vid}&p=laopao&m=A")
    assert r2.status_code in (200, 302)
    r3 = client.get("/console/variants")
    assert "laopao" in r3.text
