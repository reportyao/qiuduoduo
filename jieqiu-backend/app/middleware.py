"""轻量限流（令牌桶，进程内存；OPC 单实例足够）+ 结构化请求日志中间件。

- 公开读端点：120 req/min/IP；写端点（share/bets/auth）：30 req/min/IP
- 超限 → 429 + Retry-After
- 每请求分配 X-Request-ID，访问日志输出 JSON（grep 友好）
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("jieqiu.access")


class RateLimitMiddleware(BaseHTTPMiddleware):
    BUCKETS: dict[str, list] = {}  # key -> [tokens, last_ts]

    def __init__(self, app, read_limit: int = 120, write_limit: int = 30,
                 window_s: float = 60.0):
        super().__init__(app)
        self.read_limit = read_limit
        self.write_limit = write_limit
        self.window = window_s

    def _bucket(self, key: str, limit: int) -> float:
        now = time.time()
        b = self.BUCKETS.get(key)
        if b is None:
            self.BUCKETS[key] = [float(limit), now]
            return limit
        b[0] = min(limit, b[0] + (now - b[1]) / self.window * limit)
        b[1] = now
        return b[0]

    async def dispatch(self, request: Request, call_next):
        # 测试环境不限流（测试自身要打大量请求）
        from .config import get_settings
        if get_settings().env == "test":
            request.state.request_id = uuid.uuid4().hex[:12]
            return await call_next(request)
        # console 走自己的认证，不在此限流范围（内部工具）
        if request.url.path.startswith("/console"):
            return await call_next(request)
        ip = (request.client.host if request.client else "?")
        is_write = request.method not in ("GET", "HEAD", "OPTIONS")
        limit = self.write_limit if is_write else self.read_limit
        key = f"{ip}:{'w' if is_write else 'r'}"
        remaining = self._bucket(key, limit)
        if remaining < 1:
            return JSONResponse(
                {"detail": "请求过于频繁，稍后再试"},
                status_code=429, headers={"Retry-After": "10"})
        if remaining is not None:
            self.BUCKETS[key][0] -= 1
        request.state.request_id = uuid.uuid4().hex[:12]
        t0 = time.time()
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request.state.request_id
        logger.info(json.dumps({
            "rid": request.state.request_id, "ip": ip,
            "method": request.method, "path": request.url.path,
            "status": resp.status_code, "ms": round((time.time() - t0) * 1000, 1),
        }, ensure_ascii=False))
        return resp
