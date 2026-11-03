"""流组装：把当日判决组织成前端判决流需要的形状（对齐 UI 原型 v0.5 契约）。

分页契约（Feature-API-Mapping：GET /stream?cursor=）：cursor 为不透明游标，
next_cursor=null 表示到底。
"""
from __future__ import annotations

import base64

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SPMatch, Verdict

LESSONS = [
    {"id": "l1", "title": "为什么抽水 13% 的场次长期必亏", "minutes": 2,
     "body": "抽水是开赛前就付掉的钱。返还率 86.6% 意味着：即使判断全对，长期每 100 元亏 13.4 元。方向对也白搭——这是入场费问题。"},
    {"id": "l2", "title": "串关的概率是连乘不是相加", "minutes": 2,
     "body": "三件各自过半的事连在一起只剩六分之一。「感觉能中、实际落空」是结构常态，不是运气差。"},
    {"id": "l3", "title": "市场分歧大时，方向不重要", "minutes": 2,
     "body": "四家口径差 7pp 以上时，跟多数方向的历史命中率约 48%——和抛硬币差不多。看不懂的不碰。"},
    {"id": "l4", "title": "连败是结构，不是你不行", "minutes": 2,
     "body": "52% 置信的判断连输三次的概率约 11%。连败保护要做的不是让你更准，而是防止你在低谷加注。"},
    {"id": "l5", "title": "负 EV 是常态，靠什么活", "minutes": 2,
     "body": "有抽水就有负 EV。解球做的事是：把最差的场砍掉、把账算透明——让你只在你愿意的场次里承担成本。"},
]


def rest_day_payload(trade_date: str) -> dict:
    """F7 非比赛日：诚实空态 + 2 分钟课程（按日期轮换）。"""
    idx = sum(int(c) for c in trade_date if c.isdigit()) % len(LESSONS)
    lesson = LESSONS[idx]
    return {
        "trade_date": trade_date,
        "mode": "rest_day",
        "stats": {"total": 0, "price_fail": 0, "price_pass": 0,
                  "promoted": 0, "screening": 0, "gate_note": "非比赛日"},
        "verdicts": [],
        "next_cursor": None,
        "watch": [],
        "avoid": [],
        "onsale": [],
        "rest_day": {
            "message": "今天没有竞彩足球场次。歇一天不是放弃，是纪律的一部分。",
            "course": lesson,
        },
    }


def _enc(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _dec(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode()))
    except Exception:
        return 0


def _recent_postmortems(db: Session, limit: int = 3) -> list[dict]:
    """F12 复盘卡：最近已结算 promoted 判决 + 归因（跨日可见，非比赛日尤其需要）。"""
    from .postmortem import attribute as _attr
    settled_pm = db.scalars(
        select(Verdict).where(Verdict.status == "promoted", Verdict.settled.isnot(None))
        .order_by(Verdict.kickoff.desc()).limit(limit)
    ).all()
    return [{
        "verdict_id": v.id,
        "match_no": v.match_no,
        "match": f"{v.home} vs {v.away}",
        "trade_date": v.trade_date,
        "settled": v.settled,
        "result_score": v.result_score,
        "attribution": _attr(v)["class"],
        "note": _attr(v)["note"],
    } for v in settled_pm]


def build_stream(db: Session, trade_date: str, cursor: str | None = None,
                 limit: int = 50, user=None) -> dict:
    # F7 非比赛日：当日窗口（00:00 ~ 次日 04:59）无任何场次 → 诚实空态 + 课程 + 复盘卡
    from sqlalchemy import func
    from datetime import datetime as _dt, timedelta as _td
    try:
        next_day = (_dt.strptime(trade_date, "%Y-%m-%d") + _td(days=1)).strftime("%Y-%m-%d")
    except OverflowError:
        next_day = trade_date  # 极端日期防御（fuzz）
    n_today = db.scalar(select(func.count()).select_from(SPMatch).where(
        SPMatch.kickoff >= f"{trade_date} 00:00:00", SPMatch.kickoff <= f"{next_day} 04:59:59"))
    payload = rest_day_payload(trade_date) if not n_today else None

    if payload is not None:
        payload["postmortems"] = _recent_postmortems(db)  # 非比赛日正是看复盘的时间
        _attach_you(db, payload, user)
        return payload

    verdicts = db.scalars(
        select(Verdict).where(Verdict.trade_date == trade_date).order_by(Verdict.rake)
    ).all()

    def card(v: Verdict) -> dict:
        payload = v.payload or {}
        return {
            "id": v.id,
            "match_no": v.match_no,
            "league": v.league,
            "home": v.home,
            "away": v.away,
            "kickoff": v.kickoff,
            "pool": v.pool,
            "goal_line": v.goal_line,
            "sp": {"h": v.sp_h, "d": v.sp_d, "a": v.sp_a},
            "rake": v.rake,
            "rake_threshold": v.rake_threshold,
            "probs": {"home": v.p_home, "draw": v.p_draw, "away": v.p_away},
            "model": payload.get("model"),
            "pick": v.pick,
            "status": v.status,
            "gates": {k: g["result"] for k, g in v.gates.items()},
            "hash": v.payload_hash,
            "sealed": v.sealed_at is not None,
        }

    # 避雷：所有被砍场（任一闸 fail），按抽水深→浅排序，why = 首道死闸（F6 死因可对拍）
    killed = [v for v in verdicts if v.status == "killed"]

    def kill_why(v: Verdict) -> tuple[str, str]:
        for gate in ("price", "market", "model"):
            g = v.gates.get(gate, {})
            if g.get("result") == "fail":
                if gate == "price":
                    return gate, f"抽水 {v.rake*100:.1f}%，超当日阈值 {v.rake_threshold*100:.1f}%"
                if gate == "market":
                    div = g.get("detail", {}).get("divergence")
                    return gate, f"多源离散 {div*100:.1f}pp，超 5pp 阈值" if div is not None else "多源口径分歧超 5pp"
                return gate, f"模型置信 {g.get('detail', {}).get('top', 0)*100:.0f}%，低于 53% 可推线"
        return "price", "过闸失败"

    killed.sort(key=lambda v: v.rake, reverse=True)
    avoid = [
        {
            "match_no": v.match_no,
            "home": v.home,
            "away": v.away,
            "rake": v.rake,
            "gate": kill_why(v)[0],
            "why": kill_why(v)[1],
            "verdict_id": v.id,
        }
        for v in killed[:3]
    ]

    # 看板：过了价闸等待市/模的场，按抽水浅→深
    watch = [card(v) for v in verdicts if v.status == "screening"]

    promoted = [card(v) for v in verdicts if v.status == "promoted"]

    matches = db.scalars(select(SPMatch).where(SPMatch.match_id.in_([v.match_id for v in verdicts]))).all() if verdicts else []
    onsale = sorted(
        [
            {"match_no": m.match_no, "league": m.league, "home": m.home, "away": m.away,
             "kickoff": m.kickoff, "single": m.single_flag}
            for m in matches
        ],
        key=lambda x: x["kickoff"],
    )

    total = len(verdicts)
    price_fail = len(killed)

    # 主列表（promoted 优先，其后 watch）统一游标分页
    feed = promoted + [c for c in watch if c not in promoted]
    off = _dec(cursor)
    page = feed[off:off + limit]
    next_cursor = _enc(off + limit) if off + limit < len(feed) else None

    out = {
        "trade_date": trade_date,
        "mode": "normal",
        "generated_at": max((v.payload.get("generated_at", "") for v in verdicts), default=""),
        "stats": {
            "total": total,
            "price_fail": price_fail,
            "price_pass": total - price_fail,
            "promoted": len(promoted),
            "screening": len(watch),
            "gate_note": "三关引擎 v3：价=动态阈值 · 市=多源离散<5pp · 模=DC v1.1 收缩≥53%；国际盘/xG 源未覆盖时诚实 pending",
        },
        "verdicts": page,
        "next_cursor": next_cursor,
        "watch": watch,
        "avoid": avoid,
        "onsale": onsale,
    }
    # F12 复盘卡入流：最近已结算 promoted 判决 + 归因（跨日可见——『昨天 22:15 复盘』契约）
    out["postmortems"] = _recent_postmortems(db)
    _attach_you(db, out, user)
    return out


_STREAM_CACHE: dict[str, tuple[float, dict]] = {}
_STREAM_TTL = 15.0


def build_stream_cached(db: Session, trade_date: str, cursor: str | None = None,
                        limit: int = 50, user=None) -> dict:
    """带 15s 缓存的 build_stream：公共部分缓存，you 块按用户实时附加。"""
    import copy
    import time
    from ..config import get_settings

    if get_settings().env == "test":  # 测试要实时数据，避免跨用例污染
        return build_stream(db, trade_date, cursor, limit, user)

    key = f"{trade_date}|{cursor}|{limit}"
    now = time.time()
    hit = _STREAM_CACHE.get(key)
    if hit and now - hit[0] < _STREAM_TTL:
        payload = copy.deepcopy(hit[1])
    else:
        payload = build_stream(db, trade_date, cursor, limit, None)
        if len(_STREAM_CACHE) > 300:
            _STREAM_CACHE.clear()
        _STREAM_CACHE[key] = (now, copy.deepcopy(payload))
    if user is not None:
        _attach_you(db, payload, user)
    return payload


def _attach_you(db: Session, payload: dict, user) -> None:
    """登录用户的个性化块：休息状态 + 连败保护（F7/F11 行为面）。"""
    if user is None:
        return
    from .users import user_streak
    st = user_streak(db, user)
    payload["you"] = {
        "user_id": user.id,
        "rested": st["rested"],
        "rested_until": st["rested_until"],
        "protection_active": st["active"],
        "streak": st["streak"],
        "discipline_on": st["discipline_on"],
    }
