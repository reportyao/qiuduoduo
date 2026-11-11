"""AI 情报：Sportmonks 结构化事实 → 中文摘要；LLM 不可用时用确定性中文摘要。"""
from __future__ import annotations

import json
import logging
import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AIResearch, SPMatch, SportmonksMatchData, utcnow
from .sportmonks import _get
from .timeutil import trade_window

log = logging.getLogger(__name__)


def _fetch(fixture_id: int) -> tuple[list[str], int]:
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return [], 0
    base = settings.sportmonks_base_url.rstrip("/")
    facts: list[str] = []
    payload = _get(base, f"/match-facts/{fixture_id}",
                   f"api_token={token}&per_page=10&locale=zh")
    for row in (payload or {}).get("data") or []:
        text = row.get("natural_language")
        if text:
            facts.append(str(text)[:220])
    injured = 0
    fixture = _get(base, f"/fixtures/{fixture_id}",
                   f"api_token={token}&include=sidelined&locale=zh")
    data = (fixture or {}).get("data") or {}
    injured = len(data.get("sidelined") or [])
    return facts[:6], injured


def _extract_json(text: str) -> dict:
    """容忍 ```json 包裹、前后说明文字；只取第一个 { 到最后一个 }。"""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no json object")
    return json.loads(text[start:end + 1])


def _summarize(db: Session, facts: list[str], injured: int) -> tuple[str, list[str]]:
    if facts:
        from .llm_gateway import complete
        try:
            res = complete(
                db, "open_chat",
                [{"role": "system", "content":
                  "把给定的赛前事实翻译成简体中文，输出 JSON："
                  '{"headline":"一句话","points":["要点1","要点2"]}。'
                  "只翻译事实，不预测、不编造；最多 3 条要点。"},
                 {"role": "user", "content": json.dumps(
                     {"facts": facts, "injured_count": injured}, ensure_ascii=False)}],
                max_tokens=800,
            )
            if res is not None and not res.degraded and res.text:
                obj = _extract_json(res.text)
                headline = str(obj.get("headline") or "")[:200]
                points = [str(x)[:160] for x in (obj.get("points") or [])][:3]
                if headline:
                    return headline, points
        except Exception:  # noqa: BLE001 - 摘要失败用确定性兜底
            log.exception("intel summary failed; fallback to deterministic copy")
    headline = f"Sportmonks 赛前情报：{len(facts)} 条公开事实"
    points = [f"伤停/停赛 {injured} 人"] if injured else []
    if facts:
        points.append("原始事实为英文，中文摘要暂不可用")
    return headline, points


def sync_match(db: Session, match_id: str) -> bool:
    sm = db.get(SportmonksMatchData, match_id)
    if sm is None:
        return False
    facts, injured = _fetch(sm.fixture_id)
    row = db.get(AIResearch, match_id)
    if row is None:
        row = AIResearch(match_id=match_id)
        db.add(row)
    if not facts and not injured:
        row.status = "unavailable"
        row.headline = "暂无可用的公开情报"
        row.points = []
        row.sources = []
        row.error = ""
    else:
        headline, points = _summarize(db, facts, injured)
        row.status = "ready"
        row.headline = headline
        row.points = points
        row.sources = [{"name": "Sportmonks", "fixture_id": sm.fixture_id}]
        row.error = ""
    row.captured_at = utcnow()
    row.expires_at = row.captured_at + timedelta(hours=6)
    db.commit()
    return True


def sync_trade_date(db: Session, date: str) -> dict:
    start, end = trade_window(date)
    ids = [m.match_id for m in db.scalars(select(SPMatch).where(
        SPMatch.kickoff >= start, SPMatch.kickoff <= end)).all()]
    synced = 0
    for match_id in ids:
        if sync_match(db, match_id):
            synced += 1
    return {"ok": True, "synced": synced, "matches": len(ids)}
