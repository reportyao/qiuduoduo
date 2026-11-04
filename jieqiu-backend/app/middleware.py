"""限流（令牌桶）+ 结构化访问日志。

P0 优化（2026-11-03）：
- **按身份限流**：已登录 → user_id；设备令牌/匿名 → 令牌哈希或 IP。
  解决中国大陆 CGNAT 下「同一出口 IP 后面几十上百用户」被 120/min 误伤的问题。
- 双层防线：身份桶（读 600/分、写 60/分）+ IP 安全网（写 120/分、读 3000/分），
  防「轮换随机 token 绕过身份桶」。
- 429 带 Retry-After；成功响应带 X-RateLimit-Remaining；CORS 在外层，浏览器能看到原因。
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("jieqiu.access")


def _jwt_sub(token: str) -> str | None:
    """轻量解出 JWT sub（不查库；验签失败返回 None）。"""
    try:
        from .modules.auth import verify_access
        return verify_access(token)
    except Exception:
        return None


def identity_key(authorization: str | None, ip: str) -> str:
    """限流身份：JWT → u:<sub>；其他令牌 → t:<sha256 前 16>；无令牌 → ip:<ip>。"""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            sub = _jwt_sub(token)
            if sub:
                return f"u:{sub}"
            return "t:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    return f"ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    BUCKETS: dict[str, list] = {}  # key -> [tokens, last_ts]

    def __init__(self, app,
                 identity_read: int = 600, identity_write: int = 60,
                 ip_read_cap: int = 3000, ip_write_cap: int = 120,
                 window_s: float = 60.0):
        super().__init__(app)
        self.identity_read = identity_read
        self.identity_write = identity_write
        self.ip_read_cap = ip_read_cap
        self.ip_write_cap = ip_write_cap
        self.window = window_s

    def _take(self, key: str, limit: int) -> tuple[float, float]:
        """取一个令牌。返回 (剩余, 每秒恢复量)。"""
        now = time.time()
        if len(self.BUCKETS) > 20000:  # 回收 10 分钟未活跃的桶
            stale = [k for k, v in self.BUCKETS.items() if now - v[1] > 600]
            for k in stale[:10000]:
                self.BUCKETS.pop(k, None)
        b = self.BUCKETS.get(key)
        refill = limit / self.window
        if b is None:
            self.BUCKETS[key] = [float(limit) - 1.0, now]
            return float(limit) - 1.0, refill
        b[0] = min(float(limit), b[0] + (now - b[1]) * refill)
        b[1] = now
        if b[0] < 1.0:
            return 0.0, refill
        b[0] -= 1.0
        return b[0], refill

    async def dispatch(self, request: Request, call_next):
        from .config import get_settings
        st = get_settings()
        # 请求体上限：正常 JSON/表单都远小于 1MB；防止无界 body 打满内存。
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 1_048_576:
                    return JSONResponse({"detail": "请求体过大"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "非法 Content-Length"}, status_code=400)
        if st.env == "test":  # 测试自身要打大量请求
            request.state.request_id = uuid.uuid4().hex[:12]
            return await call_next(request)
        if request.url.path.startswith("/console"):  # 控制台自带认证与防爆破
            return await call_next(request)

        ip = request.client.host if request.client else "?"
        is_write = request.method not in ("GET", "HEAD", "OPTIONS")
        ident = identity_key(request.headers.get("authorization"), ip)

        ident_limit = self.identity_write if is_write else self.identity_read
        ip_limit = self.ip_write_cap if is_write else self.ip_read_cap

        remaining, _ = self._take(f"{ident}:{'w' if is_write else 'r'}", ident_limit)
        if remaining <= 0:
            retry = int(self.window / max(ident_limit, 1)) + 1
            return JSONResponse(
                {"detail": "请求过于频繁，稍后再试", "scope": "identity"},
                status_code=429, headers={"Retry-After": str(retry)})
        ip_remaining, _ = self._take(f"ipcap:{ip}:{'w' if is_write else 'r'}", ip_limit)
        if ip_remaining <= 0:
            return JSONResponse(
                {"detail": "请求过于频繁（出口 IP 级）", "scope": "ip"},
                status_code=429, headers={"Retry-After": "30"})

        request.state.request_id = uuid.uuid4().hex[:12]
        t0 = time.time()
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request.state.request_id
        resp.headers["X-RateLimit-Remaining"] = str(int(remaining))
        logger.info(json.dumps({
            "rid": request.state.request_id, "id": ident, "ip": ip,
            "method": request.method, "path": request.url.path,
            "status": resp.status_code, "ms": round((time.time() - t0) * 1000, 1),
        }, ensure_ascii=False))
        return resp
