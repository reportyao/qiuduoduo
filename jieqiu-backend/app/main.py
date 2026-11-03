"""FastAPI 入口。启动即建表（W2 简化；W4 换 Alembic 迁移）。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .middleware import RateLimitMiddleware
from .routers.api import router
from .routers.w4 import router as w4_router
from .routers.w6 import router as w6_router
from .routers.w7 import router as w7_router
from .routers.console import router as console_router
from .routers.w8 import router as w8_router
from .routers.auth_w5 import router as auth_router
from .routers.assistant import router as assistant_router

app = FastAPI(
    title="解球 API",
    version="0.7.0-w7",
    description="W7: F20 分享体系 · F18 双区域 · 数据导出 · 注销清除",
)
# W7 后端硬化：限流 + 结构化访问日志（内层）
app.add_middleware(RateLimitMiddleware)
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
app.include_router(router, tags=["v0.5"])
app.include_router(w4_router, tags=["v0.5-w4"])
app.include_router(w6_router, tags=["v0.5-w6"])
app.include_router(w7_router, tags=["v0.5-w7"])
app.include_router(console_router, tags=["editor-console"])
app.include_router(w8_router, tags=["w8-review"])
app.include_router(auth_router, tags=["w5-auth"])
app.include_router(assistant_router, tags=["assistant"])


def _warm_models() -> None:
    """后台预热 DC 模型（首个 /stream 请求不再等 1–2s 拟合）。"""
    try:
        import threading

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
    if get_settings().env != "test" and getattr(get_settings(), "warmup", True):
        import threading
        threading.Thread(target=_warm_models, daemon=True).start()
