"""LLM Gateway：任务路由 + 缓存 + 原子预算 + 调用账本。

设计约束（docs/llm-gateway.md）：
- 固定意图不调 LLM；只有 fallback/open_chat 才进入 fast。
- 预测/三闸/抽水不交给 LLM；结构数字仍由确定性代码产出。
- 无 key / 超时 / 超预算 / 校验失败 → degraded，由调用方走模板兜底。
- Key 只来自环境变量，永不写库、永不进日志/后台 HTML。
- 用户私有文本按 user/session 隔离缓存，禁止跨用户命中。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import LLMBudget, LLMCache, LLMProfile, LLMUsage

CN = timezone(timedelta(hours=8))
PROMPT_VER = "v1"
TASK_PROFILE = {
    "open_chat": "fast",
    "match_analysis": "deep",
    "decision_review": "deep",
    "plan_review": "fast",
    "workbench_diagnose": "fast",
}
_TTL = {
    "open_chat": 1800,
    "match_analysis": 21600,
    "decision_review": 21600,
    "plan_review": 86400,
    "workbench_diagnose": 300,
}
_PRIVATE_TASKS = {"open_chat"}
_RESERVATION_TTL_SECONDS = 600


@dataclass
class LLMResult:
    text: str | None = None
    data: dict | None = None
    provider: str = ""
    profile: str = ""
    model: str = ""
    prompt_ver: str = PROMPT_VER
    cached: bool = False
    usage: dict = field(default_factory=dict)
    degraded: bool = False
    error_class: str | None = None
    request_id: str = ""


def _settings():
    return get_settings()


def _now() -> datetime:
    return datetime.now(CN)


def _today() -> str:
    return _now().strftime("%Y-%m-%d")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


LLM_PROFILE_NAMES = ("fast", "deep")


def _env_profile(name: str) -> dict:
    st = _settings()
    if name == "deep":
        return {
            "name": "deep", "provider": st.llm_deep_provider,
            "base_url": st.llm_deep_base_url.rstrip("/"),
            "model": st.llm_deep_model, "api_key": st.llm_deep_api_key,
            "input_price": st.llm_deep_input_price_cny_per_m,
            "output_price": st.llm_deep_output_price_cny_per_m,
            "source": "env" if st.llm_deep_api_key else "none",
            "enabled": True, "reasoning": "auto",
        }
    return {
        "name": "fast", "provider": st.llm_fast_provider,
        "base_url": st.llm_fast_base_url.rstrip("/"),
        "model": st.llm_fast_model, "api_key": st.llm_fast_api_key,
        "input_price": st.llm_fast_input_price_cny_per_m,
        "output_price": st.llm_fast_output_price_cny_per_m,
        "source": "env" if st.llm_fast_api_key else "none",
        "enabled": True, "reasoning": "auto",
    }


def _admin_profile(name: str, db: Session) -> dict | None:
    """后台配置优先；未保存 Key 时回退环境变量，显式停用则不回退。"""
    row = db.get(LLMProfile, name)
    if row is None:
        return None
    base = {
        "name": name, "provider": row.provider,
        "base_url": (row.base_url or "").rstrip("/"),
        "model": row.model,
        "input_price": row.input_price_cny_per_m,
        "output_price": row.output_price_cny_per_m,
        "source": "admin", "enabled": row.enabled,
        "reasoning": getattr(row, "reasoning", "auto") or "auto",
    }
    if not row.enabled:
        return {**base, "api_key": ""}
    if not row.api_key_enc:
        return None
    from .persona_llm import decrypt_key
    key = decrypt_key(row.api_key_enc)
    if not key:
        # Key 保存过但当前加密密钥无法解开：停用而不是悄悄用 env。
        return {**base, "api_key": "", "enabled": False}
    return {**base, "api_key": key}


def _profile(name: str, db: Session | None = None) -> dict:
    if db is not None:
        override = _admin_profile(name, db)
        if override is not None:
            return override
    return _env_profile(name)


def profile_status(db: Session | None = None) -> list[dict]:
    """后台展示用：只返回是否配置/模型/端点，绝不返回 Key。"""
    out = []
    for name in LLM_PROFILE_NAMES:
        p = _profile(name, db)
        out.append({
            "name": name, "provider": p["provider"], "model": p["model"],
            "base_url": p["base_url"], "configured": bool(p["api_key"]),
            "source": p["source"], "enabled": p.get("enabled", True),
            "reasoning": p.get("reasoning", "auto"),
            "input_price_cny_per_m": p["input_price"],
            "output_price_cny_per_m": p["output_price"],
        })
    return out


def _estimate_tokens(messages: list[dict]) -> int:
    chars = sum(len(str(m.get("content", ""))) for m in messages)
    return max(1, int(chars / 1.5))


_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _redact(messages: list[dict]) -> list[dict]:
    """fast 档不接收手机号/邮箱；用户文本只做最小必要脱敏。"""
    out = []
    for m in messages:
        content = str(m.get("content", ""))
        if m.get("role") != "system":
            content = _PHONE.sub("[手机号]", content)
            content = _EMAIL.sub("[邮箱]", content)
        out.append({**m, "content": content})
    return out


def _estimate_cost(profile: dict, input_tokens: int, max_output: int) -> float:
    cost = (input_tokens * profile["input_price"] / 1_000_000
            + max_output * profile["output_price"] / 1_000_000)
    if profile["input_price"] > 0 or profile["output_price"] > 0:
        return max(cost, 0.000001)
    return 0.0


def _input_hash(task: str, messages: list[dict], schema: dict | None,
                max_tokens: int, temperature: float) -> str:
    blob = json.dumps({"task": task, "messages": messages, "schema": schema,
                       "max_tokens": max_tokens, "temperature": temperature},
                      ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_key(task: str, profile: dict, input_hash: str, scope: str,
               user_id: str | None, session_id: str) -> str:
    extra = f"{user_id or ''}:{session_id}" if scope == "user_private" else ""
    blob = "|".join([task, profile["provider"], profile["base_url"],
                     profile["model"], PROMPT_VER, input_hash, scope, extra])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_get(db: Session, key: str, now: datetime) -> dict | None:
    row = db.get(LLMCache, key)
    if row is None or row.expires_at <= now:
        return None
    row.hit_count += 1
    return dict(row.response_json or {})


def _cache_put(db: Session, key: str, task: str, profile: dict,
               input_hash: str, scope: str, data: dict, now: datetime) -> None:
    ttl = _TTL.get(task, _settings().llm_cache_ttl_seconds)
    if ttl <= 0:
        return
    db.merge(LLMCache(
        cache_key=key, task=task, profile=profile["name"],
        model=profile["model"], prompt_ver=PROMPT_VER, scope=scope,
        input_hash=input_hash, response_json=data,
        expires_at=now + timedelta(seconds=ttl),
    ))


def _ensure_budget(db: Session, day: str, task: str, profile: str,
                   limit: float) -> None:
    existing = db.scalar(select(LLMBudget).where(
        LLMBudget.day == day, LLMBudget.task == task,
        LLMBudget.profile == profile))
    if existing is not None:
        if existing.limit_cny != limit:
            existing.limit_cny = limit
        return
    try:
        with db.begin_nested():
            db.add(LLMBudget(day=day, task=task, profile=profile,
                             limit_cny=limit, reserved_cny=0.0, spent_cny=0.0))
    except Exception:
        # 并发插入撞唯一键：另一请求已建行，继续走原子 UPDATE。
        pass


def _reserve_row(db: Session, day: str, task: str, profile: str,
                 limit: float, estimate: float) -> bool:
    if estimate <= 0:
        return True
    _ensure_budget(db, day, task, profile, limit)
    # 进程在预占后崩溃会留下 reserved；超过 10 分钟的预占视为孤儿并回收。
    stale_before = _utcnow() - timedelta(seconds=_RESERVATION_TTL_SECONDS)
    db.execute(
        update(LLMBudget)
        .where(LLMBudget.day == day, LLMBudget.task == task,
               LLMBudget.profile == profile,
               LLMBudget.updated_at < stale_before)
        .values(reserved_cny=0.0))
    res = db.execute(
        update(LLMBudget)
        .where(LLMBudget.day == day, LLMBudget.task == task,
               LLMBudget.profile == profile,
               LLMBudget.spent_cny + LLMBudget.reserved_cny + estimate
               <= LLMBudget.limit_cny)
        .values(reserved_cny=LLMBudget.reserved_cny + estimate))
    return bool(res.rowcount)


def _reserve(db: Session, task: str, profile: str, estimate: float) -> bool:
    st = _settings()
    day = _today()
    if estimate <= 0:
        return True
    if not _reserve_row(db, day, "*", "*", st.llm_daily_budget_cny, estimate):
        return False
    if not _reserve_row(db, day, task, profile, st.llm_task_budget_cny, estimate):
        _release(db, task, profile, estimate)
        return False
    return True


def _release(db: Session, task: str, profile: str, estimate: float) -> None:
    if estimate <= 0:
        return
    day = _today()
    for t, p in ((task, profile), ("*", "*")):
        db.execute(
            update(LLMBudget)
            .where(LLMBudget.day == day, LLMBudget.task == t,
                   LLMBudget.profile == p)
            .values(reserved_cny=case(
                (LLMBudget.reserved_cny >= estimate,
                 LLMBudget.reserved_cny - estimate),
                else_=0.0)))


def _settle(db: Session, task: str, profile: str, estimate: float,
            actual: float) -> None:
    _release(db, task, profile, estimate)
    if actual <= 0:
        return
    day = _today()
    for t, p in ((task, profile), ("*", "*")):
        db.execute(
            update(LLMBudget)
            .where(LLMBudget.day == day, LLMBudget.task == t,
                   LLMBudget.profile == p)
            .values(spent_cny=LLMBudget.spent_cny + actual))


def _usage(db: Session, *, request_id: str, user_id: str | None,
           session_id: str, task: str, profile: str, provider: str,
           model: str, usage: dict, cost: float, latency_ms: int,
           status: str, cache_hit: bool, error_class: str | None) -> None:
    db.add(LLMUsage(
        request_id=request_id, user_id=user_id, session_id=session_id,
        task=task, profile=profile, provider=provider, model=model,
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cost_cny=cost, price_version=PROMPT_VER, latency_ms=latency_ms,
        status=status, cache_hit=cache_hit, error_class=error_class))


def _call(profile: dict, messages: list[dict], *, max_tokens: int,
          temperature: float, schema: dict | None,
          timeout_s: float | None = None) -> tuple[str, dict]:
    st = _settings()
    body: dict = {
        "model": profile["model"], "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
    }
    if profile.get("reasoning") == "off":
        body["enable_thinking"] = False
    if schema:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {profile['api_key']}",
               "Content-Type": "application/json"}
    url = profile["base_url"] + "/chat/completions"
    last: Exception | None = None
    for attempt in range(st.llm_max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_s or st.llm_timeout_s) as client:
                r = client.post(url, json=body, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < st.llm_max_retries:
                last = RuntimeError(f"http_{r.status_code}")
                continue
            r.raise_for_status()
            payload = r.json()
            text = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            raw_usage = payload.get("usage") or {}
            usage = {
                "input_tokens": raw_usage.get("prompt_tokens"),
                "output_tokens": raw_usage.get("completion_tokens"),
            }
            return text, usage
        except httpx.TimeoutException as exc:
            last = exc
            break
        except httpx.HTTPStatusError as exc:
            last = exc
            code = exc.response.status_code
            if 400 <= code < 500 and code != 429:
                break
            if attempt < st.llm_max_retries:
                continue
            break
        except Exception as exc:  # noqa: BLE001 - 归一化为 degraded，由调用方兜底
            last = exc
            if attempt < st.llm_max_retries:
                continue
            break
    raise RuntimeError(str(last or "llm_call_failed"))


def _user_calls_today(db: Session, user_id: str | None,
                      session_id: str) -> int:
    """按 CN 自然日统计用户/匿名会话的有效调用；缓存命中与拦截不计数。"""
    if not user_id and not session_id:
        return 0
    start_cn = datetime.strptime(_today(), "%Y-%m-%d").replace(tzinfo=CN)
    start_utc = start_cn.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = start_utc + timedelta(days=1)
    cond = [LLMUsage.created_at >= start_utc, LLMUsage.created_at < end_utc,
            LLMUsage.cache_hit.is_(False), LLMUsage.status != "blocked",
            LLMUsage.status != "cached"]
    if user_id:
        cond.append(LLMUsage.user_id == user_id)
    else:
        cond.append(LLMUsage.session_id == session_id)
    return int(db.scalar(select(func.count()).select_from(LLMUsage).where(*cond)) or 0)


def call_profile(profile: dict, messages: list[dict], *, max_tokens: int = 512,
                 temperature: float = 0.4, schema: dict | None = None,
                 timeout_s: float | None = None) -> tuple[str, dict]:
    """统一模型传输入口；persona pool 与 env profile 都走这里。"""
    return _call(profile, messages, max_tokens=max_tokens,
                 temperature=temperature, schema=schema, timeout_s=timeout_s)


def complete(db: Session, task: str, messages: list[dict], *,
             schema: dict | None = None, max_tokens: int = 512,
             temperature: float = 0.4, user_id: str | None = None,
             session_id: str = "", timeout_s: float | None = None) -> LLMResult:
    """调用 LLM；任何失败都返回 degraded=True，不抛业务异常。"""
    request_id = uuid.uuid4().hex
    profile_name = TASK_PROFILE.get(task)
    if profile_name is None:
        return LLMResult(degraded=True, error_class="unknown_task",
                         request_id=request_id)
    profile = _profile(profile_name, db)
    if not profile.get("enabled", True):
        return LLMResult(degraded=True, error_class="disabled",
                         provider=profile["provider"], profile=profile_name,
                         model=profile["model"],
                         request_id=request_id)
    if not profile["api_key"]:
        return LLMResult(degraded=True, error_class="not_configured",
                         provider=profile["provider"], profile=profile_name,
                         model=profile["model"],
                         request_id=request_id)

    messages = _redact(messages)
    now = _utcnow()
    scope = "user_private" if (task in _PRIVATE_TASKS and (user_id or session_id)) else "public"
    inp_hash = _input_hash(task, messages, schema, max_tokens, temperature)
    key = _cache_key(task, profile, inp_hash, scope, user_id, session_id)
    cached = _cache_get(db, key, now)
    if cached is not None:
        data = cached.get("data")
        _usage(db, request_id=request_id, user_id=user_id, session_id=session_id,
               task=task, profile=profile_name, provider=profile["provider"],
               model=profile["model"], usage={}, cost=0.0, latency_ms=0,
               status="cached", cache_hit=True, error_class=None)
        db.commit()
        return LLMResult(
            text=cached.get("text"), data=data, provider=profile["provider"],
            profile=profile_name, model=profile["model"], cached=True, degraded=False,
            request_id=request_id)

    if _user_calls_today(db, user_id, session_id) >= _settings().llm_user_daily_calls:
        _usage(db, request_id=request_id, user_id=user_id, session_id=session_id,
               task=task, profile=profile_name, provider=profile["provider"],
               model=profile["model"], usage={}, cost=0.0, latency_ms=0,
               status="blocked", cache_hit=False, error_class="user_quota")
        db.commit()
        return LLMResult(degraded=True, error_class="user_quota",
                         provider=profile["provider"], profile=profile_name,
                         model=profile["model"], request_id=request_id)

    est_in = _estimate_tokens(messages)
    est_cost = _estimate_cost(profile, est_in, max_tokens)
    if not _reserve(db, task, profile_name, est_cost):
        _usage(db, request_id=request_id, user_id=user_id, session_id=session_id,
               task=task, profile=profile_name, provider=profile["provider"],
               model=profile["model"], usage={}, cost=0.0, latency_ms=0,
               status="degraded", cache_hit=False, error_class="budget_exceeded")
        db.commit()
        return LLMResult(degraded=True, error_class="budget_exceeded",
                         provider=profile["provider"], profile=profile_name,
                         model=profile["model"],
                         request_id=request_id)

    started = time.perf_counter()
    actual_cost = 0.0
    usage: dict = {}
    settled = False
    try:
        text, usage = _call(profile, messages, max_tokens=max_tokens,
                            temperature=temperature, schema=schema,
                            timeout_s=timeout_s)
        if not (text or "").strip():
            raise RuntimeError("empty_output")
        data = None
        if schema:
            try:
                data = json.loads(text)
            except (TypeError, ValueError):
                raise RuntimeError("schema_invalid")
            if not isinstance(data, dict):
                raise RuntimeError("schema_invalid")
        in_tok = int(usage.get("input_tokens") or est_in)
        out_tok = int(usage.get("output_tokens") or 0)
        usage = {"input_tokens": in_tok, "output_tokens": out_tok}
        actual_cost = (in_tok * profile["input_price"] / 1_000_000
                       + out_tok * profile["output_price"] / 1_000_000)
        _settle(db, task, profile_name, est_cost, actual_cost)
        settled = True
        _cache_put(db, key, task, profile, inp_hash, scope,
                   {"text": text, "data": data}, now)
        _usage(db, request_id=request_id, user_id=user_id, session_id=session_id,
               task=task, profile=profile_name, provider=profile["provider"],
               model=profile["model"], usage=usage, cost=actual_cost,
               latency_ms=int((time.perf_counter() - started) * 1000),
               status="ok", cache_hit=False, error_class=None)
        db.commit()
        return LLMResult(text=text, data=data, provider=profile["provider"],
                         profile=profile_name, model=profile["model"], usage=usage,
                         request_id=request_id)
    except Exception as exc:  # noqa: BLE001 - 统一降级，不阻塞主链
        if not settled:
            _settle(db, task, profile_name, est_cost, actual_cost)
        err = str(exc)
        error_class = ("timeout" if "timed out" in err.lower() or "timeout" in err.lower()
                       else "schema_invalid" if "schema_invalid" in err
                       else "empty_output" if "empty_output" in err
                       else "provider_error")
        _usage(db, request_id=request_id, user_id=user_id, session_id=session_id,
               task=task, profile=profile_name, provider=profile["provider"],
               model=profile["model"], usage=usage, cost=actual_cost,
               latency_ms=int((time.perf_counter() - started) * 1000),
               status="degraded", cache_hit=False, error_class=error_class)
        db.commit()
        return LLMResult(degraded=True, error_class=error_class,
                         provider=profile["provider"], profile=profile_name,
                         model=profile["model"],
                         usage=usage, request_id=request_id)


def usage_summary(db: Session, day: str | None = None) -> dict:
    """后台只读用量：按 task/profile 聚合；不返回任何 Key。"""
    day = day or _today()
    start_cn = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=CN)
    start_utc = (start_cn.astimezone(timezone.utc).replace(tzinfo=None))
    end_utc = start_utc + timedelta(days=1)
    rows = db.execute(
        select(LLMUsage.task, LLMUsage.profile, func.count(),
               func.coalesce(func.sum(LLMUsage.cost_cny), 0.0),
               func.coalesce(func.sum(LLMUsage.input_tokens), 0),
               func.coalesce(func.sum(LLMUsage.output_tokens), 0),
               func.coalesce(func.sum(case((LLMUsage.cache_hit.is_(True), 1),
                                           else_=0)), 0))
        .where(LLMUsage.created_at >= start_utc,
               LLMUsage.created_at < end_utc)
        .group_by(LLMUsage.task, LLMUsage.profile)).all()
    budgets = list(db.scalars(select(LLMBudget).where(LLMBudget.day == day)
                              .order_by(LLMBudget.task)).all())
    recent = list(db.scalars(select(LLMUsage).order_by(LLMUsage.id.desc())
                             .limit(20)).all())
    return {
        "day": day,
        "rows": [
            {"task": r[0], "profile": r[1], "calls": int(r[2]),
             "cost_cny": round(float(r[3]), 4), "input_tokens": int(r[4]),
             "output_tokens": int(r[5]), "cache_hits": int(r[6])}
            for r in rows
        ],
        "budgets": [
            {"task": b.task, "profile": b.profile,
             "limit_cny": b.limit_cny, "reserved_cny": round(b.reserved_cny, 4),
             "spent_cny": round(b.spent_cny, 4)}
            for b in budgets
        ],
        "recent": [
            {"request_id": u.request_id, "task": u.task, "profile": u.profile,
             "provider": u.provider, "model": u.model,
             "status": u.status, "error_class": u.error_class,
             "cost_cny": round(u.cost_cny, 6), "latency_ms": u.latency_ms,
             "cache_hit": u.cache_hit,
             "created_at": u.created_at.isoformat() if u.created_at else None}
            for u in recent
        ],
    }
