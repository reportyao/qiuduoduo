"""F20 分享体系（素材工厂）+ F18 双区域市场配置。

分享编号可验（gate）：content_hash = sha256(规范化 payload)，share_id = 编号；
任何人 GET /share/{id} 可独立复算 —— 篡改即暴露。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ShareCard, User, Verdict
from .narrate import build_narration
from .postmortem import weekly_report
from .users import user_streak

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))


def _canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _seal(payload: dict) -> tuple[str, str, str]:
    cj = _canonical(payload)
    h = hashlib.sha256(cj.encode("utf-8")).hexdigest()
    return cj, h, h[:12]


# ---------- F18 双区域 ----------

MARKET_PROFILES = {
    "cn": {
        "region": "cn",
        "label": "中国大陆",
        "data_source": "竞彩官方（sporttery）SP · Pinnacle/Betfair/亚盘 对照",
        "currency": "CNY",
        "odds_format_default": "decimal",
        "helpline": "全国心理援助热线 12356",
        "compliance": "数据分析结果，不构成投注建议。未满 18 周岁禁止购买彩票。",
        "min_age": 18,
    },
    "global": {
        "region": "global",
        "label": "Global",
        "data_source": "Pinnacle / Betfair / the-odds-api",
        "currency": "USD",
        "odds_format_default": "decimal",
        "helpline": "BeGambleAware https://www.begambleaware.org · UK 0808 8020 133",
        "compliance": "This is data analysis, not betting advice. 18+ only. Gamble responsibly.",
        "min_age": 18,
    },
}


def market_profile(user: User | None) -> dict:
    region = (user.region if user else "cn") or "cn"
    prof = dict(MARKET_PROFILES.get(region, MARKET_PROFILES["cn"]))
    if user:
        prof["odds_format"] = user.odds_format
        prof["locale"] = user.locale
        prof["persona"] = user.persona
    return prof


# ---------- F20 素材工厂 ----------

def share_verdict(db: Session, verdict_id: str, persona: str = "zhuanjia",
                  user: User | None = None) -> tuple[ShareCard | None, str]:
    v = db.get(Verdict, verdict_id)
    if v is None:
        return None, "verdict not found"
    text, _ = build_narration(v, persona)
    payload = {
        "kind": "verdict",
        "match_no": v.match_no,
        "match": f"{v.home} vs {v.away}",
        "league": v.league,
        "trade_date": v.trade_date,
        "pool": v.pool,
        "goal_line": v.goal_line,
        "pick": v.pick,
        "status": v.status,
        "rake": v.rake,
        "text": text,
        "verdict_hash": v.payload_hash,
        "verify_url": f"/verdicts/{v.id}/seal",
    }
    return _store(db, payload, kind="verdict", user=user, verdict_id=v.id), ""


def share_weekly(db: Session, user: User) -> tuple[ShareCard | None, str]:
    rep = weekly_report(db, user.id)
    payload = {
        "kind": "weekly",
        # 不同用户即使统计相同也不能共用一张卡：否则 A 注销会删掉 B 的公开链接。
        "owner": hashlib.sha256(user.id.encode("utf-8")).hexdigest()[:12],
        "range_days": rep["range_days"],
        "promoted": rep["promoted"],
        "settled": rep["settled"],
        "wins": rep["wins"],
        "attribution": rep["attribution"],
        "killed": rep["killed"],
        "you": rep.get("you"),
        "text": (f"本周 {rep['promoted']} 推 {rep['wins']} 中。"
                 f"砍掉 {rep['killed']['killed_total']} 场（砍对 {rep['killed']['would_lose']} / "
                 f"砍错 {rep['killed']['would_win']}——都公开）。"),
    }
    return _store(db, payload, kind="weekly", user=user), ""


def share_streak(db: Session, user: User) -> tuple[ShareCard | None, str]:
    st = user_streak(db, user)
    payload = {
        "kind": "streak",
        "owner": hashlib.sha256(user.id.encode("utf-8")).hexdigest()[:12],
        "streak": st["streak"],
        "active": st["active"],
        "settled_bets": st["settled_bets"],
        "pnl": st["pnl"],
        "text": (f"当前连败 {st['streak']} 场，保护{'已触发：今天只看不下。' if st['active'] else '未触发。'}"
                 f"累计 P&L {st['pnl']} 元。"),
    }
    return _store(db, payload, kind="streak", user=user), ""


def _store(db: Session, payload: dict, kind: str, user: User | None,
           verdict_id: str | None = None) -> ShareCard:
    cj, ch, sid = _seal(payload)
    existing = db.get(ShareCard, sid)
    if existing:
        if user is not None and existing.user_id is None:
            # 先匿名分享、后登录再分享同内容：补上归属，便于 /shares/mine。
            existing.user_id = user.id
            db.commit()
        return existing  # 幂等：同内容同编号
    card = ShareCard(share_id=sid, kind=kind, user_id=user.id if user else None,
                     verdict_id=verdict_id, text=payload.get("text", ""),
                     payload=payload, content_hash=ch)
    db.add(card)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(ShareCard, sid)
        if existing is None:
            raise
        return existing
    return card


def verify_share(card: ShareCard) -> dict:
    cj, ch, sid = _seal(card.payload)
    id_matches = card.share_id == sid
    return {
        "share_id": card.share_id,
        "kind": card.kind,
        "payload": card.payload,
        "content_hash": card.content_hash,
        "recomputed_hash": ch,
        "id_matches": id_matches,
        "match": ch == card.content_hash and id_matches,
        "deep_link": f"jieqiu://share/{card.share_id}",
        "verdict_seal_url": (f"/verdicts/{card.verdict_id}/seal"
                             if card.verdict_id else None),
        "algorithm": "sha256(canonical_json)，share_id = 编号 = hash 前 12 位",
    }
