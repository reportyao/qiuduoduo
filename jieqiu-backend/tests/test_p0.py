"""P0 优化回归：身份限流 / IP 安全网 / stream 与账本缓存 / 模型预热。"""
import time

from app.middleware import identity_key


def _jwt_for(uid: str) -> str:
    import jwt as pyjwt
    from app.modules.auth import _secret
    return pyjwt.encode({"sub": uid, "typ": "access"}, _secret(), algorithm="HS256")


def test_identity_key_forms():
    tok = _jwt_for("user-1")
    assert identity_key(f"Bearer {tok}", "1.2.3.4") == "u:user-1"
    k = identity_key("Bearer some-device-token", "1.2.3.4")
    assert k.startswith("t:") and len(k) == 18
    assert identity_key(None, "1.2.3.4") == "ip:1.2.3.4"
    assert identity_key("Basic xxx", "1.2.3.4") == "ip:1.2.3.4"


def test_stream_cache_hits_and_user_block_isolated(db, monkeypatch):
    """缓存命中：基础流复用；you 块不进缓存。"""
    from app.config import Settings
    from app.modules import messaging as M
    from tests.test_deep import _mini, _promotable_match
    from app.modules.verdict import build_verdicts
    from tests.conftest import today_cn

    _mini(monkeypatch)
    _promotable_match(db, "2090001", "周日301")
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    M._STREAM_CACHE.clear()
    dev = Settings(env="dev", xg_data_path="", warmup=False)
    monkeypatch.setattr("app.config.get_settings", lambda: dev)
    from app.modules.users import login_device
    user, _ = login_device(db, "cache-user")
    s1 = M.build_stream_cached(db, today_cn(), None, 50, None)
    assert "you" not in s1
    t0 = time.time()
    s2 = M.build_stream_cached(db, today_cn(), None, 50, None)
    assert time.time() - t0 < 0.05  # 缓存命中应很快
    s3 = M.build_stream_cached(db, today_cn(), None, 50, user)
    assert "you" in s3 and "you" not in s2  # 用户块仅附加在返回副本
    assert len(M._STREAM_CACHE) == 1


def test_ledger_cache(db, client, monkeypatch):
    from app.config import Settings
    from app.routers import w4
    from tests.test_deep import _mini
    import app.routers.w4 as W
    dev = Settings(env="dev", xg_data_path="", warmup=False)
    monkeypatch.setattr("app.config.get_settings", lambda: dev)
    W._LEDGER_CACHE.clear()
    r1 = client.get("/api/ledger", params={"limit": 5})
    assert r1.status_code == 200
    r2 = client.get("/api/ledger", params={"limit": 5})
    assert r2.status_code == 200
    assert len(W._LEDGER_CACHE) == 1


def test_model_warmup_populates_cache(db, monkeypatch):
    import pandas as pd
    import tempfile, os
    from app.config import Settings
    from app.main import _warm_models
    from app.modules import verdict as vz

    rows = []
    base = pd.Timestamp("2026-09-01 20:00:00")
    for i in range(24):
        d = base + pd.Timedelta(days=i)
        rows.append(dict(datetime=d, team_home="霸主" if i % 2 == 0 else "弱旅",
                         team_away="弱旅" if i % 2 == 0 else "霸主",
                         xg_home=3.0 if i % 2 == 0 else 0.7,
                         xg_away=0.6 if i % 2 == 0 else 2.6))
    fd, path = tempfile.mkstemp(suffix=".csv"); os.close(fd)
    pd.DataFrame(rows).to_csv(path, index=False)
    st = Settings(env="test", xg_data_path=path, warmup=True)
    vz._MODEL_CACHE.clear()
    monkeypatch.setattr("app.config.get_settings", lambda: st)
    monkeypatch.setattr(vz, "get_settings", lambda: st)  # verdict 顶部已绑定该名字
    _warm_models()
    assert vz._MODEL_CACHE, "预热后模型缓存应非空"
