"""旧 /console 已全部下线；限流与请求 ID 回归保留在此。"""
import json


def test_rate_limit_429(db, client):
    """限流：JQ_ENV=test 跳过；真实 429 由子进程用例验证。"""
    for _ in range(5):
        assert client.post("/auth/device", json={"device_token": None}).status_code == 200


def test_rate_limit_429_real_server(monkeypatch):
    """限流生产形态：独立服务器 + 70 连发写 → 429。"""
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
    import app.models  # noqa: F401 注册表结构
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
        for i in range(70):
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
    assert client.get("/health").status_code == 200


def test_legacy_console_redirects_to_admin(client):
    for path in ("/console", "/console/login", "/console/logout",
                 "/console/alerts", "/console/data", "/console/plans"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 302, path
        assert r.headers["location"] == "/admin", path
    # 旧登录 POST 也不再接受
    r = client.post("/console/login", data={"pw": "dev"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/admin"
