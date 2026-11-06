"""FastAPI 入口。启动即建表（W2 简化；W4 换 Alembic 迁移）。"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse

from .db import init_db
from .middleware import RateLimitMiddleware
from .features.catalog.router import router as catalog_router
from .features.intel.router import router as intel_router
from .features.tools.router import router as tools_router
from .features.persona.router import router as persona_router
from .features.recommendations.router import router as recommendations_router
from .routers.api import router
from .routers.w4 import router as w4_router
from .routers.w6 import router as w6_router
from .routers.actions import router as actions_router
from .routers.w7 import router as w7_router
from .routers.admin_api import router as admin_api_router
from .routers.w8 import router as w8_router
from .routers.auth_w5 import router as auth_router
from .routers.collector import router as collector_router
from .features.assistant.router import router as assistant_router
from .features.compliance.router import router as compliance_router

logger = logging.getLogger("jieqiu.startup")

app = FastAPI(
    title="球多多 API",
    version="0.8.0-w8+assistant",
    description="W8 + AI 助理运行时 P0：事件监控 / 站内信 / 关注 / JPush dry-run",
)
# W7 后端硬化：限流 + 结构化访问日志（内层）
app.add_middleware(RateLimitMiddleware)
# 压缩 JSON/HTML/JS（>1KB）；移动端首屏与后台资源加载更省流量
app.add_middleware(GZipMiddleware, minimum_size=1024)
# CORS 必须最后添加 → 位于最外层：限流 429 也要带 CORS 头，否则浏览器只见 CORS 错误
import os as _os
_extra = _os.environ.get("JQ_CORS_EXTRA_ORIGINS", "").strip()
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(r"https?://(127\.0\.0\.1|localhost)(:\d+)?"
                        + (r"|" + _extra if _extra else "")),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def legacy_console_redirect(request: Request, call_next):
    """旧 /console 全部下线，统一 302 到新版运营台。"""
    path = request.url.path
    if path == "/console" or path.startswith("/console/"):
        return RedirectResponse("/admin", status_code=302)
    return await call_next(request)
# catalog 必须在 api 之前注册：/verdicts/today 不能被 /verdicts/{verdict_id} 抢先匹配。
app.include_router(catalog_router, tags=["catalog"])
app.include_router(intel_router)
app.include_router(tools_router)
app.include_router(persona_router)
app.include_router(recommendations_router)
app.include_router(router, tags=["v0.5"])
app.include_router(w4_router, tags=["v0.5-w4"])
app.include_router(w6_router, tags=["v0.5-w6"])
app.include_router(actions_router, tags=["verdict-actions"])
app.include_router(w7_router, tags=["v0.5-w7"])
app.include_router(admin_api_router, tags=["admin-ui"])
app.include_router(w8_router, tags=["w8-review"])
app.include_router(auth_router, tags=["w5-auth"])
app.include_router(assistant_router, tags=["assistant"])
app.include_router(compliance_router)
app.include_router(collector_router)


def _warm_models() -> None:
    """后台预热 DC 模型（首个 /stream 请求不再等 1–2s 拟合）。"""
    try:
        from .config import get_settings
        from .db import SessionLocal
        from .modules.align import Aligner
        from .modules.verdict import _get_model
        from datetime import datetime, timedelta, timezone

        st = get_settings()
        if not st.xg_data_path:
            return
        as_of = (datetime.now(timezone.utc).replace(tzinfo=None)
                 + timedelta(hours=st.tz_offset_hours))
        db = SessionLocal()
        try:
            _get_model(db, Aligner(db), as_of)
        finally:
            db.close()
    except Exception:
        pass


@app.on_event("startup")
def _startup() -> None:
    init_db()
    from .config import get_settings
    st = get_settings()
    if not st.odds_api_key:
        logger.warning("JQ_ODDS_API_KEY 未配置：市闸将全部 pending，推荐主链不会产出 published；"
                       "用 python -m app.odds_cli status 诊断")
    if st.env != "test" and getattr(st, "warmup", True):
        import threading
        threading.Thread(target=_warm_models, daemon=True).start()
