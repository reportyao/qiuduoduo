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

app = FastAPI(
    title="解球 API",
    version="0.7.0-w7",
    description="W7: F20 分享体系 · F18 双区域 · 数据导出 · 注销清除",
)
# CORS：本地演示页（8777）与未来 App WebView 跨源调用（W7 review 抓到缺失）
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)
# W7 后端硬化：限流 + 结构化访问日志
app.add_middleware(RateLimitMiddleware)
app.include_router(router, tags=["v0.5"])
app.include_router(w4_router, tags=["v0.5-w4"])
app.include_router(w6_router, tags=["v0.5-w6"])
app.include_router(w7_router, tags=["v0.5-w7"])
app.include_router(console_router, tags=["editor-console"])
app.include_router(w8_router, tags=["w8-review"])


@app.on_event("startup")
def _startup() -> None:
    init_db()
