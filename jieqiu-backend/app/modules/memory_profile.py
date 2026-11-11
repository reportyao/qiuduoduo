"""低成本行为/偏好记忆：从已有事件推导用户画像，不做逐请求 LLM。"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Bet, Memory, SPMatch, UserProfileFeature,
                      WatchTarget, utcnow)


def _upsert(db: Session, user_id: str, feature: str, value: str,
            confidence: float = 0.8, source: str = "behavior") -> None:
    if not value:
        return
    row = db.scalar(select(UserProfileFeature).where(
        UserProfileFeature.user_id == user_id,
        UserProfileFeature.feature == feature,
    ))
    if row is None:
        row = UserProfileFeature(user_id=user_id, feature=feature)
        db.add(row)
    row.value = value[:256]
    row.confidence = max(0.0, min(1.0, confidence))
    row.source = source
    row.updated_at = utcnow()


def refresh(db: Session, user_id: str) -> list[UserProfileFeature]:
    """从显式记忆 + 注单 + 关注推导 top 特征。"""
    teams: Counter[str] = Counter()
    leagues: Counter[str] = Counter()
    bets = list(db.scalars(select(Bet).where(Bet.user_id == user_id)).all())
    verdicts = {}
    if bets:
        from ..models import Verdict
        verdicts = {v.id: v for v in db.scalars(select(Verdict).where(
            Verdict.id.in_([b.verdict_id for b in bets]))).all()}
    for bet in bets:
        v = verdicts.get(bet.verdict_id)
        if v is not None:
            teams[v.home] += 1
            teams[v.away] += 1
            leagues[v.league] += 1
    watches = list(db.scalars(select(WatchTarget).where(
        WatchTarget.user_id == user_id)).all())
    match_ids = [w.target_id for w in watches if w.target_type == "match"]
    if match_ids:
        for m in db.scalars(select(SPMatch).where(SPMatch.match_id.in_(match_ids))).all():
            teams[m.home] += 1
            teams[m.away] += 1
            leagues[m.league] += 1
    for mem in db.scalars(select(Memory).where(
            Memory.user_id == user_id, Memory.category == "preference")).all():
        if "主队" in mem.key or "球队" in mem.key:
            _upsert(db, user_id, "team_affinity", mem.value, 1.0, "explicit")
        if "风险" in mem.key or "偏好" in mem.key:
            _upsert(db, user_id, "risk_preference", mem.value, 1.0, "explicit")
    if teams:
        team, count = teams.most_common(1)[0]
        _upsert(db, user_id, "team_affinity", team, min(1.0, 0.5 + count / 10))
    if leagues:
        league, count = leagues.most_common(1)[0]
        _upsert(db, user_id, "league_affinity", league, min(1.0, 0.5 + count / 10))
    db.commit()
    return list(db.scalars(select(UserProfileFeature).where(
        UserProfileFeature.user_id == user_id).order_by(
        UserProfileFeature.confidence.desc())).all())


def context(db: Session, user_id: str) -> list[dict]:
    rows = refresh(db, user_id)
    return [{"feature": r.feature, "value": r.value,
             "confidence": r.confidence, "source": r.source}
            for r in rows[:5]]
