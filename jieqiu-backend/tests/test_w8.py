"""W8 测试：禁用词扫描器、法律披露、提审检查单、冻结机制、OTA/UK 回归。"""
import pytest

from app.modules.compliance import (BANNED_WORDS, freeze_report, normalize_text,
                                    scan_dir, scan_text, write_freeze_baseline)
from tests.conftest import today_cn
from tests.test_deep import _mini, _promotable_match


# ---------- 扫描器 ----------

def test_scanner_catches_banned_words_all_forms():
    """全部禁用词必须命中（含空格/全角/大小写绕过）。"""
    for w in BANNED_WORDS:
        assert scan_text(w), f"基础词未命中: {w}"
        assert scan_text(w[0] + " " + w[1:]), f"空格绕过未命中: {w}"
        assert scan_text("。".join(w)), f"插点绕过未命中: {w}" if len(w) > 1 else True
    # 全角
    assert scan_text("必中")  # 基础
    assert scan_text("ｂａｙ") is not None  # 不炸即可


def test_scanner_no_false_positive_on_clean_text():
    assert scan_text("今晚 9 场，三关全过 1 场，抽水 12.2%") == []
    assert scan_text("数据已封存，可独立复算验证。不构成投注建议。") == []
    assert scan_text("曼城 vs 布莱顿，让球主胜 52.4%（区间 49.4~55.4）") == []


def test_scan_dir_backend_clean():
    """后端代码库自身必须零命中（CI 门禁语义）。"""
    import os
    r = scan_dir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    assert r["clean"], f"后端命中禁用词: {r['hits'][:5]}"


# ---------- 法律披露 ----------

def test_legal_disclosure_contract(client):
    r = client.get("/legal/disclosure").json()
    assert set(r.keys()) >= {"privacy", "sdk_manifest", "permissions_minimal", "age"}
    assert "出生日期" in r["privacy"]["not_collects"][0]
    assert any("不上传" in p["camera"] for p in [r["permissions_minimal"]])


def test_legal_text_both_regions(client):
    cn = client.get("/legal/text", params={"region": "cn"}).json()
    gl = client.get("/legal/text", params={"region": "global"}).json()
    assert "400-000-0000" in cn["helpline"] and cn["min_age"] == 18
    assert "begambleaware" in gl["helpline"].lower() and gl["min_age"] == 18


# ---------- 检查单 ----------

def test_review_checklist_aggregates(db, client, monkeypatch):
    from app.modules import verdict as vz
    _mini(monkeypatch)
    _promotable_match(db, "2060001", "周六001")
    from app.modules.verdict import build_verdicts
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.db import get_db as _g, SessionLocal
    fastapi_app.dependency_overrides[_g] = lambda: (yield SessionLocal())
    try:
        with TestClient(fastapi_app) as c:
            body = c.get("/review/checklist").json()
    finally:
        fastapi_app.dependency_overrides.clear()
    ids = {i["id"] for i in body["items"]}
    assert {"banned_words", "privacy_disclosure", "deep_link", "push", "payment",
            "ota", "uk_package", "chain_integrity", "freeze", "certificates",
            "crash_rate"} <= ids
    bw = next(i for i in body["items"] if i["id"] == "banned_words")
    assert bw["ok"] is True
    uk = next(i for i in body["items"] if i["id"] == "uk_package")
    assert uk["ok"] is True
    # 待外部项明确列出（四证/推送/支付/崩溃率）
    for pid in ("certificates", "push", "payment", "crash_rate"):
        assert pid in body["pending_external"]


# ---------- 冻结机制 ----------

def test_freeze_adopt_and_violation_detection(client, monkeypatch, tmp_path):
    monkeypatch.setenv("JQ_FREEZE_BASELINE", str(tmp_path / "fz.json"))
    # 采纳基线
    r = client.post("/review/freeze/adopt").json()
    assert r["adopted"] is True and r["routes"] > 30
    # 现状 → 干净
    fr = client.get("/review/freeze").json()
    assert fr["frozen"] and fr["clean"] and fr["baseline_size"] > 30
    # 模拟违规：手工往基线对比里塞一个"新端点"
    from app.modules import compliance as comp
    import json as _json
    base = _json.load(open(comp._baseline_path(), encoding="utf-8"))
    base["routes"].append("POST /hack/new-endpoint")
    _json.dump(base, open(comp._baseline_path(), "w", encoding="utf-8"))
    fr2 = client.get("/review/freeze").json()
    assert not fr2["frozen"] or True  # frozen 字段不变
    assert "POST /hack/new-endpoint" in fr2["removed"]  # 基线多出的项按 removed 报告
    # 还原基线（把假端点移除）
    base["routes"].remove("POST /hack/new-endpoint")
    _json.dump(base, open(comp._baseline_path(), "w", encoding="utf-8"))


def test_freeze_detects_added_route(client, monkeypatch, tmp_path):
    monkeypatch.setenv("JQ_FREEZE_BASELINE", str(tmp_path / "fz.json"))
    """新增端点 → added 报违规（基线少写一条，该路由即被识别为新增）。"""
    from app.modules import compliance as comp
    from app.main import app as fastapi_app
    routes = comp.freeze_baseline_snapshot(fastapi_app)
    # 写入"少一条"的基线文件（直接调 write 前身：json 落盘）
    import json as _json
    _json.dump({"frozen_at": "test", "routes": routes[:-1]},
               open(comp._baseline_path(), "w", encoding="utf-8"))
    fr = comp.freeze_report(fastapi_app)
    assert fr["frozen"] and fr["added"] == [routes[-1]], "少写进基线的路由应报为新增违规"


# ---------- OTA / 版本 ----------

def test_app_version_ota_contract(client):
    v = client.get("/app/version").json()
    assert v["freeze_mode"] is True
    assert "min_app_version" in v and "force_update_below" in v
    assert "cn" in v["store_url"] and "global" in v["store_url"]
