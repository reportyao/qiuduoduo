"""人设语气翻译：模型池 + 加密 Key + failover + 缓存。

设计约束：
- 只做“语气翻译”，不生成方向/概率/条件/数字；调用方传入 canonical 文本。
- 发布前批量生成，不在用户请求时现调；前端只读缓存/模板。
- egg-alpha 失败时自动切到 neohorse-1-9b；连续失败进入冷却，避免每单都等超时。
- Key 加密落库，后台只显示“已配置”。
"""
from __future__ import annotations

import base64
import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import LLMUsage, PersonaCopyCache, PersonaLLMModel, Verdict
from . import persona_registry

PROMPT_VER = "persona-v1"

PERSONAS = {
    "zhuanjia": {
        "name": "理性专家",
        "address": "你",
        "style": "冷静、克制、结论先行；短句；不用 emoji；不煽动。",
    },
    "laopao": {
        "name": "感性老炮",
        "address": "兄弟",
        "style": "口语、接地气、有情绪但不煽动；可以损友式提醒；不打包票。",
    },
    "meng": {
        "name": "萌妹",
        "address": "主人",
        "style": "亲近、勤快、短句、少量语气词和颜文字；方向必须说清楚，不能暧昧。",
    },
}


class PersonaLLMError(RuntimeError):
    pass


class PersonaLLMNotConfigured(PersonaLLMError):
    pass


@dataclass
class PersonaCopyResult:
    text: str
    model: str
    persona: str
    cached: bool = False
    latency_ms: int = 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fernet() -> Fernet:
    st = get_settings()
    secret = st.persona_llm_enc_key or st.jwt_secret or "jieqiu-persona-dev"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_key(raw: str) -> str:
    if not raw:
        return ""
    return _fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_key(enc: str) -> str:
    if not enc:
        return ""
    try:
        return _fernet().decrypt(enc.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_key(enc: str) -> str:
    return "已配置" if enc else "未配置"


def _system_prompt(persona: str, db=None) -> str:
    p = PERSONAS[persona]
    name, address, style = p["name"], p["address"], p["style"]
    max_chars = 220
    emoji_policy, allowed_emoji = "none", ""
    if db is not None:
        row = persona_registry.get_profile(db, persona)
        if row is not None:
            name = row.name or name
            address = row.address or address
            style = row.style_prompt or style
            max_chars = row.max_chars or max_chars
            emoji_policy = row.emoji_policy or emoji_policy
            allowed_emoji = row.allowed_emoji or allowed_emoji
    return chr(10).join([
        "你是球多多的“语气翻译器”，不是分析师。",
        "输入是一段已经确定的事实文本。你只负责改写语气，不得新增、删除或改变："
        "方向、概率、条件、失效条件、成本、组合腿数、日期。",
        "输入中的每个数字必须原样保留；不得新增任何数字；不得写收益承诺或绝对化保证。",
        f"人设：{name}；称呼：{address}；风格：{style}",
        f"输出不超过 {max_chars} 个汉字；不要新增段落。",
        f"emoji 策略：{emoji_policy}；允许的 emoji：{allowed_emoji or '无'}。",
        "只能改写，不得添加输入中没有的建议、安慰、免责声明、责任声明、下注指令或结果判断；"
        "不要写“不打包票/别怪我/你自己决定”这类话；尽量逐句对应，不要扩写。",
        "只输出改写后的中文纯文本：不要解释、不要 Markdown、不要引号、不要 JSON。",
        "如果输入信息不足，保留“暂不明确/观望”，不要补编。",
    ])

_EXTRA_DISCLAIMER = re.compile(
    r"(?:^|[，。；！？!?])\s*[^。！？!?]*"
    r"(?:不打包票|别怪我|自个儿掂量|你自己决定|风险自担|盈亏自负)"
    r"[^。！？!?]*[。！？!?]?")


def _clean_output(text: str) -> str:
    text = (text or "").strip().strip("\"'“”‘’")
    cleaned = _EXTRA_DISCLAIMER.sub("", text).strip()
    cleaned = cleaned.lstrip("，。；！？!? ").strip()
    return cleaned or text


def _model_base(base_url: str) -> str:
    return (base_url or get_settings().persona_llm_base_url).rstrip("/")


_SECRET_RE = re.compile(r"sk[-_][A-Za-z0-9_\-]{8,}")


def _scrub_error(value: str) -> str:
    return _SECRET_RE.sub("sk-***", str(value))[:240]


def _provider_name(base_url: str) -> str:
    try:
        return urlparse(base_url).netloc or "persona"
    except ValueError:
        return "persona"


def ensure_default_models(db: Session) -> int:
    """首次访问播种默认模型；key 来自 env，不写死在源码。"""
    st = get_settings()
    key = encrypt_key(st.persona_llm_api_key)
    existing = list(db.scalars(select(PersonaLLMModel)).all())
    if existing:
        # 首次启动时 env 没 key，后来补 key：回填空 key 的默认模型。
        changed = 0
        if key:
            for row in existing:
                if row.model in ("egg-alpha", "neohorse-1-9b") and not row.api_key_enc:
                    row.api_key_enc = key
                    changed += 1
        if changed:
            db.commit()
        return 0
    defaults = [
        ("Egg Alpha", "egg-alpha", 10),
        ("NeoHorse 1 9B", "neohorse-1-9b", 20),
    ]
    for name, model, priority in defaults:
        db.add(PersonaLLMModel(
            name=name, base_url=st.persona_llm_base_url, model=model,
            api_key_enc=key, priority=priority, enabled=True,
            timeout_s=st.persona_llm_timeout_s,
            max_tokens=st.persona_llm_max_tokens,
            temperature=st.persona_llm_temperature,
        ))
    db.commit()
    return len(defaults)


def list_models(db: Session) -> list[PersonaLLMModel]:
    ensure_default_models(db)
    return list(db.scalars(select(PersonaLLMModel)
                           .order_by(PersonaLLMModel.priority, PersonaLLMModel.id)).all())


def add_model(db: Session, *, name: str, base_url: str, model: str,
              api_key: str = "", priority: int = 100,
              timeout_s: int | None = None,
              max_tokens: int | None = None,
              temperature: float | None = None) -> PersonaLLMModel:
    st = get_settings()
    base_url = (base_url or st.persona_llm_base_url).strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise PersonaLLMError("base_url 必须是 http(s)")
    if not model.strip():
        raise PersonaLLMError("model 不能为空")
    row = PersonaLLMModel(
        name=(name or model).strip(), base_url=base_url, model=model.strip(),
        api_key_enc=encrypt_key(api_key.strip()), priority=priority,
        enabled=True, timeout_s=timeout_s or st.persona_llm_timeout_s,
        max_tokens=max_tokens or st.persona_llm_max_tokens,
        temperature=st.persona_llm_temperature if temperature is None else temperature,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PersonaLLMError("同一 base_url + model 已存在")
    db.refresh(row)
    return row


def toggle_model(db: Session, model_id: int) -> bool:
    row = db.get(PersonaLLMModel, model_id)
    if row is None:
        raise PersonaLLMError("model not found")
    row.enabled = not row.enabled
    db.commit()
    return row.enabled


def update_key(db: Session, model_id: int, api_key: str) -> PersonaLLMModel:
    row = db.get(PersonaLLMModel, model_id)
    if row is None:
        raise PersonaLLMError("model not found")
    row.api_key_enc = encrypt_key((api_key or "").strip())
    row.fail_count = 0
    row.last_error = None
    row.last_error_at = None
    db.commit()
    db.refresh(row)
    return row


def delete_model(db: Session, model_id: int) -> None:
    row = db.get(PersonaLLMModel, model_id)
    if row is None:
        raise PersonaLLMError("model not found")
    db.delete(row)
    db.commit()


def _cache_hash(db: Session, source_hash: str, persona: str) -> str:
    profile = persona_registry.get_profile(db, persona)
    version = profile.version if profile is not None else 1
    return hashlib.sha256(
        f"{source_hash}|{persona}|{version}|{PROMPT_VER}".encode("utf-8")
    ).hexdigest()


def get_cached(db: Session, source_key: str, source_hash: str,
               persona: str) -> PersonaCopyResult | None:
    effective = _cache_hash(db, source_hash, persona)
    row = db.scalar(select(PersonaCopyCache).where(
        PersonaCopyCache.source_key == source_key,
        PersonaCopyCache.source_hash == effective,
        PersonaCopyCache.persona == persona))
    if row is None or not row.text:
        return None
    return PersonaCopyResult(text=row.text, model=row.model, persona=persona, cached=True)


def _circuit_open(row: PersonaLLMModel, now: datetime) -> bool:
    if row.fail_count < 3 or row.last_error_at is None:
        return False
    return (now - row.last_error_at).total_seconds() < get_settings().persona_llm_cooldown_s


def _call_model(row: PersonaLLMModel, text: str, persona: str,
                db=None) -> tuple[str, dict, int]:
    key = decrypt_key(row.api_key_enc)
    if not key:
        raise PersonaLLMNotConfigured("API Key 未配置")
    # 统一走 llm_gateway 的模型传输层；persona 仍保留自己的模型池/熔断/缓存。
    from .llm_gateway import call_profile
    profile = {
        "name": f"persona:{row.model}",
        "provider": "persona",
        "base_url": _model_base(row.base_url),
        "model": row.model,
        "api_key": key,
        "input_price": 0.0,
        "output_price": 0.0,
    }
    messages = [
        {"role": "system", "content": _system_prompt(persona, db)},
        {"role": "user", "content": text},
    ]
    started = time.perf_counter()
    try:
        content, usage = call_profile(
            profile, messages,
            max_tokens=row.max_tokens or get_settings().persona_llm_max_tokens,
            temperature=row.temperature,
            timeout_s=row.timeout_s or get_settings().persona_llm_timeout_s,
        )
    except Exception as exc:  # noqa: BLE001 - 统一转换为 persona 领域异常
        raise PersonaLLMError(str(exc)) from exc
    latency = int((time.perf_counter() - started) * 1000)
    content = _clean_output(content)
    if not content:
        raise PersonaLLMError("模型返回空文本")
    return content, usage or {}, latency


def _log_usage(db: Session, row: PersonaLLMModel, *, persona: str,
               text: str, usage: dict, latency: int, status: str,
               error_class: str | None = None, data: dict | None = None) -> None:
    cost = 0.0
    try:
        cost = float((data or {}).get("cost_cny") or 0)
    except (TypeError, ValueError):
        cost = 0.0
    db.add(LLMUsage(
        request_id=hashlib.sha256(f"{row.id}:{persona}:{time.time()}".encode()).hexdigest()[:32],
        task="persona_translate", profile="persona", provider=_provider_name(row.base_url),
        model=row.model,
        input_tokens=int((usage or {}).get("prompt_tokens") or 0),
        output_tokens=int((usage or {}).get("completion_tokens") or 0),
        cost_cny=cost, latency_ms=latency, status=status,
        cache_hit=False, error_class=error_class,
    ))


def translate(db: Session, text: str, persona: str, *,
              source_key: str = "", source_hash: str = "",
              use_cache: bool = True) -> PersonaCopyResult:
    """按优先级调用模型池；失败自动切换；连续失败冷却。"""
    if persona not in PERSONAS:
        raise PersonaLLMError("persona 必须是 zhuanjia/laopao/meng")
    text = (text or "").strip()
    if not text:
        raise PersonaLLMError("待翻译文本为空")

    if use_cache and source_key and source_hash:
        cached = get_cached(db, source_key, source_hash, persona)
        if cached is not None:
            return cached

    ensure_default_models(db)
    rows = list(db.scalars(select(PersonaLLMModel)
                           .where(PersonaLLMModel.enabled.is_(True))
                           .order_by(PersonaLLMModel.priority, PersonaLLMModel.id)).all())
    if not rows:
        raise PersonaLLMNotConfigured("人设模型池为空")

    now = _utcnow()
    errors: list[str] = []
    for row in rows:
        if _circuit_open(row, now):
            errors.append(f"{row.model}: cooling_down")
            continue
        try:
            output, usage, latency = _call_model(row, text, persona, db=db)
            row.fail_count = 0
            row.last_error = None
            row.last_error_at = None
            row.last_ok_at = now
            if source_key and source_hash:
                effective = _cache_hash(db, source_hash, persona)
                cached = db.scalar(select(PersonaCopyCache).where(
                    PersonaCopyCache.source_key == source_key,
                    PersonaCopyCache.source_hash == effective,
                    PersonaCopyCache.persona == persona))
                if cached is None:
                    db.add(PersonaCopyCache(
                        source_key=source_key, source_hash=_cache_hash(db, source_hash, persona),
                        persona=persona, text=output, model=row.model,
                        latency_ms=latency))
                else:
                    cached.text = output
                    cached.model = row.model
                    cached.latency_ms = latency
            _log_usage(db, row, persona=persona, text=text, usage=usage,
                       latency=latency, status="ok")
            db.commit()
            return PersonaCopyResult(text=output, model=row.model,
                                     persona=persona, latency_ms=latency)
        except PersonaLLMError as exc:
            row.fail_count += 1
            row.last_error = _scrub_error(str(exc))
            row.last_error_at = now
            _log_usage(db, row, persona=persona, text=text, usage={},
                       latency=0, status="degraded", error_class=type(exc).__name__)
            errors.append(f"{row.model}: {exc}")
            db.commit()
            continue
    raise PersonaLLMError("全部模型失败: " + "; ".join(errors[:4]))


def canonical_verdict_text(v: Verdict) -> str:
    """从判决构造中性事实文本，供语气翻译使用。"""
    pick = (v.pick or {}).get("dir") or "暂无明确方向"
    model = max((v.model_h or 0, v.model_d or 0, v.model_a or 0), default=0)
    rake = f"{v.rake * 100:.1f}%" if v.rake is not None else "待同步"
    state = {"promoted": "三关全过", "screening": "复核中", "killed": "不推"}.get(
        v.status, v.status)
    return (
        f"比赛：{v.home} vs {v.away}（{v.match_no}）。"
        f"状态：{state}。方向：{pick}。"
        f"模型最高概率：{model * 100:.1f}%。"
        f"官方抽水：{rake}。"
        f"这是统计判断，不是结果承诺。"
    )


def warm_verdicts(db: Session, trade_date: str,
                  personas: tuple[str, ...] = ("zhuanjia", "laopao", "meng")) -> dict:
    """预生成某日三套人设文案；由 cron/CLI 调用，用户请求只读缓存。"""
    verdicts = list(db.scalars(select(Verdict)
                               .where(Verdict.trade_date == trade_date)).all())
    ok = 0
    failed = 0
    errors: list[str] = []
    for v in verdicts:
        source_hash = v.payload_hash or hashlib.sha256(
            canonical_verdict_text(v).encode("utf-8")).hexdigest()
        for persona in personas:
            try:
                translate(db, canonical_verdict_text(v), persona,
                          source_key=f"verdict:{v.id}", source_hash=source_hash)
                ok += 1
            except PersonaLLMError as exc:
                failed += 1
                errors.append(f"{v.id}/{persona}: {exc}")
    return {"date": trade_date, "verdicts": len(verdicts),
            "ok": ok, "failed": failed, "errors": errors[:8]}
