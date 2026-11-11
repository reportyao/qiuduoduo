"""API 路由：health / stream / verdicts。只读接口，W2 无鉴权（公开数据）。"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..features.intel import service as intel_service
from ..models import (DecisionSnapshot, IntlOdds, ModelRun, SPMatch,
                       SPSnapshot, TeamAlias, Verdict)
from ..modules.messaging import build_stream_cached
from ..modules.timeutil import (trade_date_from_kickoff, trade_date_now,
                                trade_window)

router = APIRouter()

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))
_ON_SALE_CACHE: dict[str, tuple[float, dict]] = {}
_ON_SALE_TTL = 15.0
_ON_SALE_LOCK = threading.Lock()


def cn_now() -> datetime:
    return datetime.now(CN)


@router.get("/health")
def health(detailed: bool = False, db: Session = Depends(get_db)):
    """轻量存活检查；?detailed=1 才做全表计数（大表 COUNT 不应在探针里跑）。"""
    import time
    started = time.perf_counter()
    db.scalar(select(1))
    db_latency_ms = round((time.perf_counter() - started) * 1000, 2)
    backend = db.bind.dialect.name if db.bind is not None else "unknown"
    # 数据同步延迟（F17 gate：同步延迟 <5min 达标率 99% 的观测基础）
    last_snap = db.scalar(select(SPSnapshot.captured_at).order_by(SPSnapshot.captured_at.desc()).limit(1))
    sync_lag_seconds = None
    if last_snap:
        try:
            last_dt = datetime.strptime(last_snap[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=CN)
            sync_lag_seconds = int((cn_now() - last_dt).total_seconds())
        except ValueError:
            pass
    # 链健康（断链告警的可观测入口，gate：断链告警演练通过）
    from ..modules.sealchain import latest_chain_status
    chain = latest_chain_status(db)
    return {
        "status": "ok",
        "env": get_settings().env,
        "time_cn": cn_now().isoformat(),
        "sync_lag_seconds": sync_lag_seconds,
        "chain": chain,
        "sources": {
            "sporttery": last_snap or None,
            "the_odds_api": "configured" if get_settings().odds_api_key else "not_configured",
        },
        "db": {"backend": backend, "latency_ms": db_latency_ms},
        **({"counts": {
            "sp_matches": db.scalar(select(func.count()).select_from(SPMatch)) or 0,
            "sp_snapshots": db.scalar(select(func.count()).select_from(SPSnapshot)) or 0,
            "team_aliases": db.scalar(select(func.count()).select_from(TeamAlias)) or 0,
            "verdicts": db.scalar(select(func.count()).select_from(Verdict)) or 0,
            "intl_odds": db.scalar(select(func.count()).select_from(IntlOdds)) or 0,
            "published_today": db.scalar(
                select(func.count()).select_from(DecisionSnapshot).where(
                    DecisionSnapshot.trade_date == trade_date_now(cn_now()),
                    DecisionSnapshot.status == "published",
                    or_(DecisionSnapshot.expires_at.is_(None),
                        DecisionSnapshot.expires_at
                        > datetime.now(CN).replace(tzinfo=None)))) or 0,
        }} if detailed else {}),
    }


@router.get("/stream")
def stream(date: str | None = None, cursor: str | None = None, limit: int = 50,
           authorization: str | None = Header(default=None),
           db: Session = Depends(get_db)):
    """判决流。date 缺省 = 今天（CN）；cursor 游标分页；带 token 时附 you 块（F7/F11）。"""
    d = date or trade_date_now(cn_now())
    try:
        parsed = datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")
    if parsed.year > 2100:
        raise HTTPException(422, "date 超出支持范围")  # fuzz：9999-12-31 +1d 溢出防护
    limit = max(1, min(limit, 200))
    from ..modules.users import user_from_token, is_deleted
    user = user_from_token(db, authorization)
    if user is not None and is_deleted(user):
        user = None  # 注销冷静期 → 按匿名处理（you 块不泄露）
    return build_stream_cached(db, d, cursor=cursor, limit=limit, user=user)


@router.get("/analysis-log")
def analysis_log(date: str | None = None, match_id: str | None = None,
                 limit: int = 100, db: Session = Depends(get_db)):
    """引擎分析日志（UI「引擎状态」弹层）：当日各场各闸最新一次结果，按时间倒序。"""
    d = date or trade_date_now(cn_now())
    try:
        parsed = datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")
    if parsed.year > 2100:
        raise HTTPException(422, "date 超出支持范围")
    limit = max(1, min(limit, 500))
    from ..models import ModelRun
    q = select(ModelRun).where(ModelRun.run_date == d)
    if match_id:
        q = q.where(ModelRun.match_id == match_id)
    rows = db.scalars(q.order_by(ModelRun.created_at.desc(), ModelRun.id.desc())).all()
    latest: dict[tuple[str, str], ModelRun] = {}
    for r in rows:  # 倒序遍历，首见即最新（created_at 同秒时 id 大者胜）
        latest.setdefault((r.match_id, r.gate), r)
    mids = {mid for (mid, _g) in latest}
    matches = {m.match_id: m for m in db.scalars(
        select(SPMatch).where(SPMatch.match_id.in_(mids)))} if mids else {}
    entries = []
    for (match_id, gate), r in sorted(
        latest.items(), key=lambda kv: (kv[1].created_at, kv[1].id), reverse=True
    )[:limit]:
        m = matches.get(match_id)
        entries.append({
            "match_id": match_id,
            "match_no": m.match_no if m else "",
            "match": f"{m.home} vs {m.away}" if m else "",
            "gate": gate,
            "result": r.result,
            "detail": r.detail,
            "time": r.created_at.isoformat(),
        })
    return {"date": d, "total": len(latest), "entries": entries}


@router.get("/matches/on-sale")
def matches_on_sale(db: Session = Depends(get_db)):
    """今日在售（竞彩规则：当日及次日 04:59 前开赛），带抽水与三关状态（F17）。"""
    now = cn_now()
    today = trade_date_now(now)
    use_cache = get_settings().env != "test"
    if use_cache:
        with _ON_SALE_LOCK:
            cached = _ON_SALE_CACHE.get(today)
        if cached and (time.time() - cached[0]) < _ON_SALE_TTL:
            return cached[1]
    start, end = trade_window(today)
    rows = db.scalars(
        select(SPMatch).where(SPMatch.kickoff >= max(start, now.strftime("%Y-%m-%d %H:%M:%S")),
                               SPMatch.kickoff <= end).order_by(SPMatch.kickoff)
    ).all()
    # 同一场比赛可能跨竞彩日：取该 match 最新日期的判决，
    # 避免 00:00–04:59 场次在“今天”日期下丢失 status/verdict_id。
    match_ids = [m.match_id for m in rows]
    latest: dict[str, Verdict] = {}
    if match_ids:
        for v in db.scalars(
                select(Verdict).where(Verdict.match_id.in_(match_ids))
                .order_by(Verdict.trade_date)):
            latest[v.match_id] = v
    verdicts = latest
    matches = []
    now_dt = cn_now()
    for m in rows:
        v = verdicts.get(m.match_id)
        trade_date = v.trade_date if v else trade_date_from_kickoff(m.kickoff) or today
        matches.append({
            "match_id": m.match_id,
            "match_no": m.match_no, "league": m.league, "home": m.home, "away": m.away,
            "kickoff": m.kickoff, "sale_close": m.kickoff, "single": m.single_flag,
            "rake": v.rake if v else None,
            "gates": {k: g["result"] for k, g in v.gates.items()} if v else None,
            "status": v.status if v else None,
            "verdict_id": v.id if v else None,
            "coverage": intel_service.build_coverage_brief(
                db, m, trade_date, v, now_dt),
        })
    result = {"date": today, "count": len(rows), "matches": matches}
    if use_cache:
        with _ON_SALE_LOCK:
            _ON_SALE_CACHE[today] = (time.time(), result)
            if len(_ON_SALE_CACHE) > 20:
                for old_key in list(_ON_SALE_CACHE)[:-10]:
                    _ON_SALE_CACHE.pop(old_key, None)
    return result


@router.get("/matches/sale-schedule")
def sale_schedule(db: Session = Depends(get_db)):
    """停售时间表（F10）：竞彩足球停售时刻 = 开赛时刻，官方口径零误差。"""
    now = cn_now()
    today = trade_date_now(now)
    start, end = trade_window(today)
    rows = db.scalars(
        select(SPMatch).where(SPMatch.kickoff >= max(start, now.strftime("%Y-%m-%d %H:%M:%S")),
                               SPMatch.kickoff <= end).order_by(SPMatch.kickoff)
    ).all()
    return {
        "date": today,
        "rule": "竞彩足球：停售时刻 = 官方开赛时刻（sporttery matchTime，采集器直取）",
        "items": [
            {"match_no": m.match_no, "home": m.home, "away": m.away,
             "sale_close": m.kickoff, "kickoff": m.kickoff}
            for m in rows
        ],
    }


@router.get("/verdicts/{verdict_id}/evidence")
def verdict_evidence(verdict_id: str, db: Session = Depends(get_db)):
    """判断依据卡（F3）：每条证据均含来源与时间，可溯源。"""
    v = db.get(Verdict, verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    return {
        "id": v.id,
        "match_no": v.match_no,
        "evidence": (v.payload or {}).get("evidence", []),
        "data_cutoff": v.payload.get("data_cutoff") if v.payload else None,
    }


@router.get("/matches/{match_id}/why-not")
def why_not(match_id: str, date: str | None = None, db: Session = Depends(get_db)):
    """为什么不推（F6）：死因完全由闸门日志/判决 gates 派生，可对拍 model_runs。"""
    d = date or trade_date_now(cn_now())
    m = db.get(SPMatch, match_id)
    if m is None:
        raise HTTPException(404, "match not found")
    v = db.scalar(select(Verdict).where(Verdict.match_id == match_id,
                                        Verdict.trade_date == d))
    if v is None:
        # 深链/关注可能拿的是日历日期而不是竞彩日；回退到该场最新判决。
        v = db.scalar(select(Verdict).where(Verdict.match_id == match_id)
                      .order_by(Verdict.trade_date.desc()).limit(1))
    if v is None:
        raise HTTPException(404, "no verdict for this match")
    if v.status == "promoted":
        return {"status": "promoted", "verdict_id": v.id, "match_no": m.match_no,
                "home": m.home, "away": m.away, "note": "三关全过，已在判决流中"}

    order = ["price", "market", "model"]
    failed = next((g for g in order if v.gates.get(g, {}).get("result") == "fail"), None)
    pending = next((g for g in order if v.gates.get(g, {}).get("result") == "pending_data"), None)
    gate = failed or pending
    is_fail = failed is not None
    g = v.gates.get(gate, {}) if gate else {}

    fail_titles = {
        "price": f"死于「价」：抽水 {v.rake*100:.1f}% 超当日阈值 {v.rake_threshold*100:.1f}%",
        "market": "死于「市」：多源口径分歧超 5pp",
        "model": "死于「模」：模型置信不足",
    }
    pending_titles = {
        "market": "复核中 · 等「市」：国际盘源未覆盖（配置 the-odds-api key 即启用）",
        "model": "复核中 · 等「模」：xG 强度表未覆盖该对阵（本季数据接入后自动重评）",
        "price": "复核中",
    }
    whatifs = {
        "price": "若官方 SP 因资金压力调整使抽水收窄至阈值内，自动重新入池。",
        "market": "若国际盘收敛（离散度 < 5pp）或数据源接入，自动重新入池并推送。",
        "model": "若 xG 强度表覆盖该对阵（或窗口数据足够），自动重评。",
    }
    runs = db.scalars(select(ModelRun).where(ModelRun.match_id == match_id,
                                             ModelRun.run_date == v.trade_date)).all()
    return {
        "status": v.status,
        "match_no": m.match_no, "league": m.league,
        "home": m.home, "away": m.away,
        "dead_gate": gate,
        "verdict_kind": "fail" if is_fail else ("pending" if pending else None),
        "title": (fail_titles if is_fail else pending_titles).get(gate, "复核中"),
        "gates": v.gates,
        "detail": g,
        "whatif": whatifs.get(gate, ""),
        "audit": {
            "model_runs": [{"gate": r.gate, "result": r.result,
                            "detail": r.detail} for r in runs],
            "verdict_hash": v.payload_hash,
        },
    }


def _devig(h: float, d: float, a: float) -> dict | None:
    try:
        inv = [1.0 / float(h), 1.0 / float(d), 1.0 / float(a)]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    total = sum(inv)
    if total <= 0:
        return None
    return {"home": inv[0] / total, "draw": inv[1] / total, "away": inv[2] / total}


def _probability_compare(db: Session, v: Verdict) -> dict:
    """详情页概率对比：竞彩去水 / 模型 / 国际盘基准。没有的项返回 null。"""
    sp = _devig(v.sp_h, v.sp_d, v.sp_a)
    model_raw = (v.payload or {}).get("model") or {}
    has_model = bool(model_raw.get("shrunk"))
    model = (
        {"home": v.p_home, "draw": v.p_draw, "away": v.p_away}
        if has_model else None
    )
    market = None
    match = db.get(SPMatch, v.match_id)
    if match is not None:
        from ..modules.intl_odds import sources_for_match
        rows = sources_for_match(db, match)
        if rows:
            row = rows[0]
            probs = _devig(row.sp_h, row.sp_d, row.sp_a)
            if probs:
                label = {"pinnacle": "Pinnacle", "consensus": "共识"}.get(
                    row.source, row.source)
                market = {"bookmaker": label, "probs": probs}
    return {
        "sp": sp,
        "model": model,
        "market": market,
        "model_enabled": has_model,
        "reason": None if has_model else "本场没有可用的模型概率；仅展示竞彩与市场参考。",
        "data_cutoff": (v.payload or {}).get("data_cutoff"),
    }


@router.get("/verdicts/{verdict_id}")
def verdict_detail(verdict_id: str, db: Session = Depends(get_db)):
    v = db.get(Verdict, verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    return {
        "id": v.id,
        "trade_date": v.trade_date,
        "match_no": v.match_no,
        "league": v.league,
        "home": v.home,
        "away": v.away,
        "kickoff": v.kickoff,
        "pool": v.pool,
        "goal_line": v.goal_line,
        "sp": {"h": v.sp_h, "d": v.sp_d, "a": v.sp_a},
        "probs": {"home": v.p_home, "draw": v.p_draw, "away": v.p_away},
        "probability_compare": _probability_compare(db, v),
        "rake": v.rake,
        "status": v.status,
        "gates": v.gates,
        "model": (v.payload or {}).get("model"),
        "pick": v.pick,
        "payload": v.payload,
        "payload_hash": v.payload_hash,
        "sealed_at": v.sealed_at.isoformat() if v.sealed_at else None,
        "created_at": v.created_at.isoformat(),
    }


@router.get("/verdicts/{verdict_id}/seal")
def verdict_seal(verdict_id: str, db: Session = Depends(get_db)):
    """封存详情：任何人可独立复算 sha256 验证（F2 gate）；附修订史与链位（单条可验链）。"""
    v = db.get(Verdict, verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    from ..models import VerdictRevision

    cj, digest = _reseal(v.payload)
    revs = db.scalars(
        select(VerdictRevision).where(VerdictRevision.verdict_id == verdict_id)
        .order_by(VerdictRevision.id)
    ).all()
    latest_rev = revs[-1] if revs else None
    return {
        "id": v.id,
        "algorithm": "sha256(canonical_json)",
        "canonical_form": "json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',',':')) utf-8",
        "payload": v.payload,
        "recomputed_hash": digest,
        "stored_hash": v.payload_hash,
        "match": digest == v.payload_hash,
        "chain": {"prev": latest_rev.chain_prev if latest_rev else "",
                  "hash": latest_rev.chain_hash if latest_rev else "",
                  "verify": "/chain/verify"},
        "revision_count": len(revs),
        "revisions": [
            {"hash": r.payload_hash, "data_cutoff": r.data_cutoff,
             "chain_hash": r.chain_hash, "sealed_at": r.created_at.isoformat()}
            for r in revs
        ],
        "verify_hint": (
            "python3 -c \"import json,hashlib;p=json.load(open('payload.json'));"
            "print(hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())\""
        ),
    }


def _reseal(payload: dict) -> tuple[str, str]:
    from ..modules.verdict import seal_payload

    return seal_payload(payload)
