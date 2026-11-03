"""W8 端点：法律披露 / 提审检查单 / 冻结基线 / App 版本(OTA)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..modules.compliance import (DISCLOSURE, freeze_report, review_checklist,
                                  scan_text, write_freeze_baseline)

router = APIRouter()


@router.get("/legal/disclosure")
def legal_disclosure():
    """隐私弹窗 + SDK 清单 + 权限最小化声明（App 首启拉取此契约渲染弹窗）。"""
    return DISCLOSURE


@router.get("/legal/text")
def legal_text(region: str = "cn"):
    """按区域返回法定文案（弹窗/关于页直接渲染）。"""
    from ..modules.share import MARKET_PROFILES
    prof = MARKET_PROFILES.get(region) or MARKET_PROFILES["cn"]
    return {"region": prof["region"], "helpline": prof["helpline"],
            "compliance": prof["compliance"], "min_age": prof["min_age"],
            "data_source": prof["data_source"]}


@router.get("/app/version")
def app_version():
    """OTA/最低版本判定（App 启动时调用）。"""
    from ..config import get_settings
    return {
        "api": "0.8.0-w8+assistant",
        "min_app_version": "0.5.0",
        "force_update_below": "0.5.0",
        "store_url": {"cn": "https://appgallery.huawei.com/", "global": "https://apps.apple.com/"},
        "freeze_mode": True,
    }


@router.get("/review/checklist")
def review_checklist_api(db: Session = Depends(get_db)):
    from ..main import app as fastapi_app
    return review_checklist(db, fastapi_app)


@router.get("/review/banned-words/scan")
def review_scan_text(text: str):
    """即席扫描：给一段商店文案，返回是否可提交（提审前自检工具）。"""
    hits = scan_text(text)
    return {"ok": not hits, "hits": hits,
            "verdict": "PASS" if not hits else f"FAIL：命中 {len(hits)} 个禁用词"}


@router.post("/review/freeze/adopt")
def freeze_adopt():
    """采纳当前路由集合为冻结基线（W8 开始时执行一次）。"""
    from ..main import app as fastapi_app
    n = write_freeze_baseline(fastapi_app)
    return {"adopted": True, "routes": n,
            "note": "冻结期新增端点将被 /review/freeze 标记为违规"}


@router.get("/review/freeze")
def freeze_status():
    from ..main import app as fastapi_app
    return freeze_report(fastapi_app)
