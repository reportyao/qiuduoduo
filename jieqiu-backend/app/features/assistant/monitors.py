"""监控规则：只生成事件，不做用户扇出。

P0：结论变化、停售提醒、终场、结算、每日简报。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import (AssistantState, Event, MatchResult, SPMatch, Verdict,
                      VerdictRevision)
from .events import emit_event

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))


def cn_now() -> datetime:
    return datetime.now(CN)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_state(db: Session, key: str) -> str | None:
    row = db.get(AssistantState, key)
    return row.value if row else None


def _set_state(db: Session, key: str, value: str) -> None:
    row = db.get(AssistantState, key)
    if row is None:
        db.add(AssistantState(key=key, value=value))
    else:
        row.value = value
    db.commit()


def _prob(payload: dict | None) -> float:
    p = payload or {}
    pick = p.get("pick") or {}
    if pick.get("prob") is not None:
        try:
            return float(pick["prob"])
        except (TypeError, ValueError):
            pass
    shrunk = (p.get("model") or {}).get("shrunk")
    if shrunk:
        try:
            return max(float(x) for x in shrunk)
        except (TypeError, ValueError):
            pass
    return 0.0


def _pick_dir(payload: dict | None) -> str:
    pick = (payload or {}).get("pick") or {}
    return str(pick.get("dir", "") or "")


def scan_verdict_changes(db: Session, backfill: bool = False, limit: int = 200) -> int:
    """扫描新修订，只在结论真的变化时生成事件。"""
    last_raw = _get_state(db, "last_revision_id")
    if last_raw is None:
        max_id = db.scalar(select(func.max(VerdictRevision.id))) or 0
        if not backfill:
            _set_state(db, "last_revision_id", str(max_id))
            return 0
        last = 0
    else:
        last = int(last_raw)
    revs = db.scalars(
        select(VerdictRevision).where(VerdictRevision.id > last)
        .order_by(VerdictRevision.id).limit(limit)
    ).all()
    made = 0
    for rev in revs:
        v = db.get(Verdict, rev.verdict_id)
        if v is None:
            last = rev.id
            continue
        cur = rev.payload or {}
        status = cur.get("status") or v.status
        prev = db.scalar(
            select(VerdictRevision)
            .where(VerdictRevision.verdict_id == rev.verdict_id,
                   VerdictRevision.id < rev.id)
            .order_by(VerdictRevision.id.desc()).limit(1)
        )
        prev_payload = prev.payload if prev else None
        prev_status = (prev_payload or {}).get("status", "")
        prob, prev_prob = _prob(cur), _prob(prev_payload)
        pick, prev_pick = _pick_dir(cur), _pick_dir(prev_payload)
        status_changed = bool(prev_payload) and status != prev_status
        pick_changed = bool(prev_payload) and pick != prev_pick
        prob_moved = bool(prev_payload) and abs(prob - prev_prob) > 0.01
        if prev_payload is None:
            if status not in ("promoted", "killed"):
                last = rev.id
                continue
        elif status == "screening" and not status_changed:
            last = rev.id
            continue
        elif not (status_changed or pick_changed or prob_moved):
            last = rev.id
            continue

        etype = ("verdict_promoted" if status == "promoted"
                 else "verdict_killed" if status == "killed"
                 else "verdict_change")
        payload = {
            "verdict_id": v.id, "match_id": v.match_id, "match_no": v.match_no,
            "home": v.home, "away": v.away, "kickoff": v.kickoff,
            "status": status, "prev_status": prev_status,
            "pick": cur.get("pick"), "prev_pick": (prev_payload or {}).get("pick"),
            "prob": round(prob, 4), "prev_prob": round(prev_prob, 4),
            "delta_pp": round((prob - prev_prob) * 100, 1),
            "payload_hash": rev.payload_hash,
        }
        _, created = emit_event(
            db, type=etype, dedupe_key=f"verdict:{rev.id}",
            severity=2 if status_changed else 1,
            match_id=v.match_id, payload=payload,
            data_cutoff=rev.data_cutoff or "",
        )
        made += int(created)
        last = rev.id
    if revs:
        _set_state(db, "last_revision_id", str(last))
    return made


def scan_close_soon(db: Session, now_cn: datetime | None = None,
                    window_min: int = 10) -> int:
    now = now_cn or cn_now()
    end = now + timedelta(minutes=window_min)
    rows = db.scalars(
        select(SPMatch).where(SPMatch.kickoff >= now.strftime("%Y-%m-%d %H:%M:%S"),
                              SPMatch.kickoff <= end.strftime("%Y-%m-%d %H:%M:%S"))
    ).all()
    made = 0
    for m in rows:
        try:
            ko = datetime.strptime(m.kickoff, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
        except ValueError:
            continue
        minutes = max(1, int((ko - now).total_seconds() // 60))
        kickoff_utc = ko.astimezone(timezone.utc).replace(tzinfo=None)
        _, created = emit_event(
            db, type="close_soon", dedupe_key=f"close:{m.match_id}:{now.strftime('%Y-%m-%d')}",
            severity=2, match_id=m.match_id,
            payload={"match_id": m.match_id, "match_no": m.match_no, "home": m.home,
                     "away": m.away, "kickoff": m.kickoff, "minutes": minutes},
            data_cutoff=now.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at=kickoff_utc,
        )
        made += int(created)
    return made


def scan_final(db: Session, now_cn: datetime | None = None) -> int:
    """终场事件：用赛果反查判决；没有 live feed 时作为终场事实源。"""
    now = now_cn or cn_now()
    since = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = db.scalars(
        select(MatchResult).where(MatchResult.match_date >= since)
        .order_by(MatchResult.id.desc()).limit(100)
    ).all()
    made = 0
    for r in rows:
        try:
            d = datetime.strptime(r.match_date, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        # 赛果日期是欧洲当地日；判决 kickoff 是 CN 时间，取 ±1 天窗口避免串到历史同对阵
        low = (d - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        high = (d + timedelta(days=2)).strftime("%Y-%m-%d 00:00:00")
        v = db.scalar(
            select(Verdict).where(Verdict.home == r.home, Verdict.away == r.away,
                                  Verdict.kickoff >= low, Verdict.kickoff < high)
            .order_by(Verdict.kickoff.desc()).limit(1)
        )
        if v is None:
            continue
        score = f"{r.goals_home}-{r.goals_away}"
        _, created = emit_event(
            db, type="final", dedupe_key=f"final:{v.match_id}", severity=2,
            match_id=v.match_id,
            payload={"verdict_id": v.id, "match_id": v.match_id, "match_no": v.match_no,
                     "home": v.home, "away": v.away, "score": score,
                     "goals_home": r.goals_home, "goals_away": r.goals_away},
            data_cutoff=r.retrieved_at or now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        made += int(created)
    return made


def scan_settlements(db: Session, now_cn: datetime | None = None) -> int:
    now = now_cn or cn_now()
    since = now.astimezone(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
    rows = db.scalars(
        select(Verdict).where(Verdict.settled.isnot(None), Verdict.settled_at.isnot(None),
                              Verdict.settled_at >= since)
        .order_by(Verdict.settled_at.desc()).limit(1000)
    ).all()
    made = 0
    for v in rows:
        _, created = emit_event(
            db, type="settled", dedupe_key=f"settle:{v.id}", severity=1,
            match_id=v.match_id,
            payload={"verdict_id": v.id, "match_id": v.match_id, "match_no": v.match_no,
                     "home": v.home, "away": v.away, "result": v.settled,
                     "score": v.result_score or ""},
            data_cutoff=str(v.settled_at or ""),
        )
        made += int(created)
    return made


def scan_daily_brief(db: Session, now_cn: datetime | None = None) -> int:
    now = now_cn or cn_now()
    hour = int(os.environ.get("JQ_DAILY_BRIEF_HOUR", "19"))
    if now.hour < hour:
        return 0
    date = now.strftime("%Y-%m-%d")
    nxt = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    total = db.scalar(select(func.count()).select_from(SPMatch).where(
        SPMatch.kickoff >= f"{date} 00:00:00", SPMatch.kickoff <= f"{nxt} 04:59:59")) or 0
    verdicts = db.scalars(select(Verdict).where(Verdict.trade_date == date)).all()
    promoted = sum(1 for v in verdicts if v.status == "promoted")
    screening = sum(1 for v in verdicts if v.status == "screening")
    killed = sum(1 for v in verdicts if v.status == "killed")
    _, created = emit_event(
        db, type="daily_brief", dedupe_key=f"daily:{date}", severity=0,
        payload={"date": date, "total": total, "promoted": promoted,
                 "screening": screening, "killed": killed},
        data_cutoff=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return int(created)


def run_monitors(db: Session, backfill: bool = False) -> dict:
    return {
        "verdict": scan_verdict_changes(db, backfill=backfill),
        "close": scan_close_soon(db),
        "final": scan_final(db),
        "settled": scan_settlements(db),
        "daily": scan_daily_brief(db),
    }
