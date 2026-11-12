"""AI 情报：Sportmonks 结构化事实 → 中文摘要；LLM 不可用时用确定性中文摘要。"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (AIResearch, SPMatch, SportmonksFixtureIntel,
                      SportmonksMatchData, utcnow)
from .sportmonks import _get
from .timeutil import CN, trade_window

log = logging.getLogger(__name__)


def effective_status(row: AIResearch, now=None) -> str:
    """ready 但过期的情报不能再当最新情报展示。"""
    current = now or utcnow()
    if row.status == "ready" and row.expires_at is not None:
        expires = row.expires_at
        if expires.tzinfo is not None:
            expires = expires.astimezone(timezone.utc).replace(tzinfo=None)
        if expires <= current:
            return "expired"
    return row.status


def _fetch(fixture_id: int, db: Session | None = None,
           match_id: str | None = None) -> tuple[list[str], int]:
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return [], 0
    base = settings.sportmonks_base_url.rstrip("/")
    facts: list[str] = []
    payload = _get(base, f"/match-facts/{fixture_id}",
                   f"api_token={token}&per_page=100&include=type&locale=zh")
    for row in (payload or {}).get("data") or []:
        text = row.get("natural_language")
        if text:
            facts.append(str(text)[:220])
    injured = 0
    intel = db.get(SportmonksFixtureIntel, match_id) if db and match_id else None
    structured = (intel.payload or {}) if intel else {}
    if structured:
        lineups = structured.get("lineups") or {}
        home_line = lineups.get("home") or {}
        away_line = lineups.get("away") or {}
        if home_line.get("starters") and away_line.get("starters"):
            home_names = "、".join(
                p.get("name") for p in home_line["starters"][:4] if p.get("name"))
            away_names = "、".join(
                p.get("name") for p in away_line["starters"][:4] if p.get("name"))
            facts.append(
                f"首发：{home_line.get('team_name')} {home_line.get('formation') or ''} "
                f"（{home_names}）；{away_line.get('team_name')} "
                f"{away_line.get('formation') or ''}（{away_names}）"
            )
        sidelined = structured.get("sidelined") or []
        injured = len(sidelined)
        if sidelined:
            facts.append("伤停：" + "、".join(
                f"{row.get('player_name')}（{row.get('type_label')}）"
                for row in sidelined[:6] if row.get("player_name")))
        standings = structured.get("standings") or {}
        for side in ("home", "away"):
            row = standings.get(side) or {}
            if row:
                facts.append(
                    f"积分榜：{home_line.get('team_name') if side == 'home' else away_line.get('team_name')} "
                    f"第{row.get('position')}，{row.get('points')}分，近况 "
                    f"{' '.join(row.get('form') or []) or '—'}"
                )
        weather = structured.get("weather") or {}
        venue = structured.get("venue") or {}
        if venue:
            facts.append(
                f"场地：{venue.get('name') or '—'}，{venue.get('city') or '—'}，"
                f"容量 {venue.get('capacity') or '—'}"
            )
        if weather:
            facts.append(
                f"天气：{weather.get('description') or '—'}，"
                f"日间 {(weather.get('temperature') or {}).get('day', '—')}°C，"
                f"风速 {(weather.get('wind') or {}).get('speed', '—')}"
            )
        main_ref = (structured.get("referees") or {}).get("main") or {}
        if main_ref:
            facts.append(f"主裁：{main_ref.get('name') or '—'}")
        _raw_highlights = structured.get("prediction_highlights") or []
        highlights = _raw_highlights if isinstance(_raw_highlights, list) else (
            _raw_highlights.get("items") or [])
        for item in highlights[:3]:
            values = item.get("values") or {}
            if item.get("key") == "CORRECT_SCORE_PROBABILITY":
                text = "、".join(
                    f"{row.get('score')} {row.get('probability')}%"
                    for row in (item.get("scores") or [])[:2])
            else:
                text = " / ".join(f"{key} {value}%" for key, value in values.items()
                                  if isinstance(value, (int, float)))
            if text:
                facts.append(f"Sportmonks 预测参考（{item.get('label')}）：{text}")
    else:
        fixture = _get(base, f"/fixtures/{fixture_id}",
                       f"api_token={token}&include=sidelined&locale=zh")
        data = (fixture or {}).get("data") or {}
        injured = len(data.get("sidelined") or [])
    return facts[:12], injured


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
                  "只翻译事实，不预测、不编造；事实写“首发”就是已公布，不要改写成“预计”；"
                  "最多 5 条要点。"},
                 {"role": "user", "content": json.dumps(
                     {"facts": facts, "injured_count": injured}, ensure_ascii=False)}],
                max_tokens=800,
            )
            if res is not None and not res.degraded and res.text:
                obj = _extract_json(res.text)
                headline = str(obj.get("headline") or "")[:200]
                points = [str(x)[:160] for x in (obj.get("points") or [])][:5]
                if any("首发" in fact for fact in facts):
                    # 事实包已写“首发”，LLM 不得降级成“预计首发”。
                    def confirmed(text: str) -> str:
                        return (text.replace("预计采用", "采用")
                                .replace("预计排出", "排出")
                                .replace("预计首发", "首发")
                                .replace("预计阵容", "阵容"))
                    headline = confirmed(headline)
                    points = [confirmed(point) for point in points]
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
    facts, injured = _fetch(sm.fixture_id, db=db, match_id=match_id)
    facts_hash = hashlib.sha256(json.dumps(
        {"facts": facts, "injured": injured}, ensure_ascii=False,
        sort_keys=True).encode("utf-8")).hexdigest()
    row = db.get(AIResearch, match_id)
    now = utcnow()
    # 事实没变且缓存仍在有效期：不重复调 LLM，只续期。确定性兜底文案不算有效缓存。
    if (row is not None and row.status == "ready" and row.facts_hash == facts_hash
            and row.expires_at is not None and row.expires_at > now
            and row.headline and not row.headline.startswith("Sportmonks 赛前情报：")):
        row.captured_at = now
        row.expires_at = now + timedelta(hours=6)
        db.commit()
        return True
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
    row.facts_hash = facts_hash
    row.captured_at = now
    row.expires_at = now + timedelta(hours=6)
    db.commit()
    return True


def sync_trade_date(db: Session, date: str) -> dict:
    start, end = trade_window(date)
    now_cn = datetime.now(CN).strftime("%Y-%m-%d %H:%M:%S")
    ids = [m.match_id for m in db.scalars(select(SPMatch).where(
        SPMatch.kickoff >= max(start, now_cn),
        SPMatch.kickoff <= end)).all()]
    synced = 0
    for match_id in ids:
        if sync_match(db, match_id):
            synced += 1
    return {"ok": True, "synced": synced, "matches": len(ids)}
