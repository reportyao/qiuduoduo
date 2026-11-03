"""封存哈希链 + 每日公开锚定（W4 核心承诺的技术底座）。

结构：
- 修订链：每条 verdict_revision 的 chain_hash = sha256(chain_prev + payload_hash + created_at)
  链首的 chain_prev = 前一日锚根（无则 GENESIS）—— 日与日之间也被锁住
- 日锚点：root = sha256(排序后的全部 chain_hash 串联 + date + count)，锚与锚相链
- 验证：重算整条链与锚根，任何一处被改 → broken_at 定位到第几节

当日锚点为临时（随修订追加刷新），次日冻结。
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DailyAnchor, VerdictRevision, utcnow

GENESIS = "GENESIS"


def chain_link(prev: str, payload_hash: str, created_at_iso: str) -> str:
    raw = f"{prev}|{payload_hash}|{created_at_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ts(dt) -> str:
    """链时间戳规范化：统一去时区（SQLite 往返会剥 offset，两侧必须同形）。"""
    if dt is None:
        return utcnow().replace(tzinfo=None).isoformat()
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.isoformat()


def _prev_day_root(db: Session, date: str) -> str:
    row = db.scalar(
        select(DailyAnchor).where(DailyAnchor.date < date).order_by(DailyAnchor.date.desc()).limit(1)
    )
    return row.root_hash if row else GENESIS


def link_revision(db: Session, rev: VerdictRevision) -> None:
    """修订落档时接入链（build_verdicts 在 add 后调用；幂等：已有 chain_hash 不重算）。

    链首 = 同日最后一节；当日首节 = 前一日锚根（无则 GENESIS）—— 日界由锚锁定。
    """
    if rev.chain_hash:
        return
    db.flush()  # autoflush=False：让同批次先落档的修订在查询中可见（链必须逐节相扣）
    date = (rev.payload or {}).get("trade_date", "")
    day_revs = [r for r in _day_revisions(db, date) if r.id != rev.id]  # 排除自身
    last = day_revs[-1] if day_revs else None
    if last is not None and last.id != rev.id and last.chain_hash:
        rev.chain_prev = last.chain_hash
    else:
        rev.chain_prev = _prev_day_root(db, date) or GENESIS
    rev.chain_hash = chain_link(rev.chain_prev, rev.payload_hash, _ts(rev.created_at))
    db.flush()


def rebuild_day_chain(db: Session, date: str) -> int:
    """重建某日全部修订的链（幂等修复用）。返回链节数。"""
    revs = _day_revisions(db, date)
    prev = _prev_day_root(db, date) or GENESIS
    for rev in revs:
        rev.chain_prev = prev
        rev.chain_hash = chain_link(prev, rev.payload_hash, _ts(rev.created_at))
        prev = rev.chain_hash
    db.commit()
    return len(revs)


def _day_revisions(db: Session, date: str) -> list[VerdictRevision]:
    """某日修订：优先走冗余 trade_date 列（索引）；历史 NULL 行回退 payload 扫描。"""
    indexed = db.scalars(
        select(VerdictRevision).where(VerdictRevision.trade_date == date)
        .order_by(VerdictRevision.id)
    ).all()
    if indexed:
        return list(indexed)
    legacy = db.scalars(
        select(VerdictRevision).where(VerdictRevision.trade_date.is_(None))
        .order_by(VerdictRevision.id)
    ).all()
    return [r for r in legacy if (r.payload or {}).get("trade_date") == date]


def backfill_revision_dates(db: Session) -> int:
    """把历史修订的 trade_date 冗余列补齐（一次性；seed 启动时调用）。"""
    legacy = db.scalars(
        select(VerdictRevision).where(VerdictRevision.trade_date.is_(None))
    ).all()
    n = 0
    for r in legacy:
        d = (r.payload or {}).get("trade_date")
        if d:
            r.trade_date = d
            n += 1
    if n:
        db.commit()
    return n


def build_anchor(db: Session, date: str) -> DailyAnchor:
    """构建/刷新当日锚点（seed 每轮调用；跨日自动相链）。"""
    revs = _day_revisions(db, date)
    if not revs:
        return db.get(DailyAnchor, date)
    # 确保该日全部修订已接链
    for rev in revs:
        if not rev.chain_hash:
            link_revision(db, rev)
    db.commit()
    joined = "|".join(r.chain_hash for r in sorted(revs, key=lambda x: x.id))
    count = len(revs)
    prev_root = _prev_day_root(db, date)
    root = hashlib.sha256(f"{prev_root}|{date}|{count}|{joined}".encode("utf-8")).hexdigest()
    a = db.get(DailyAnchor, date)
    if a is None:
        a = DailyAnchor(date=date)
        db.add(a)
    a.root_hash = root
    a.revision_count = count
    a.prev_root = prev_root
    db.commit()
    return a


_CHAIN_CACHE: dict[str, tuple[float, dict]] = {}


def latest_chain_status(db: Session, ttl_seconds: float = 60.0) -> dict:
    """最新锚点日的链健康摘要（seed 告警 + /health 可观测用）。

    TTL 缓存：/health 被秒级轮询，整链重算 O(日修订数) 不该每次打。
    """
    import time as _time
    a = db.scalar(select(DailyAnchor).order_by(DailyAnchor.date.desc()).limit(1))
    if a is None:
        return {"date": None, "ok": True, "links": 0, "broken_at": None, "note": "尚无锚点"}
    # 内容指纹：id+payload_hash 全量（轻量列）→ 篡改/追加任何修订都会失效缓存
    import hashlib as _h
    rows = db.execute(
        select(VerdictRevision.id, VerdictRevision.payload_hash)
        .where(VerdictRevision.trade_date == a.date)
        .order_by(VerdictRevision.id)).all()
    fp = _h.sha256("|".join(f"{i}:{hh}" for i, hh in rows).encode()).hexdigest()[:16]
    key = f"{a.date}:{a.root_hash}:{fp}"
    cached = _CHAIN_CACHE.get(key)
    if cached and _time.time() - cached[0] < ttl_seconds:
        return cached[1]
    rep = verify_day(db, a.date)
    out = {"date": a.date, "ok": rep["ok"], "links": rep["links"],
           "broken_at": rep["broken_at"], "anchor_match": rep["anchor_match"]}
    _CHAIN_CACHE.clear()  # 只保留最新锚点
    _CHAIN_CACHE[key] = (_time.time(), out)
    return out


def verify_day(db: Session, date: str) -> dict:
    """独立复算整日链 + 锚根。篡改定位到第几节。"""
    revs = _day_revisions(db, date)
    prev = _prev_day_root(db, date) or GENESIS
    broken_at = None
    for i, rev in enumerate(revs):
        expect = chain_link(prev, rev.payload_hash, _ts(rev.created_at))
        if expect != rev.chain_hash:
            broken_at = i
            break
        prev = expect
    anchor = db.get(DailyAnchor, date)
    anchor_match = False
    recomputed_root = None
    if revs and anchor:
        joined = "|".join(r.chain_hash for r in sorted(revs, key=lambda x: x.id))
        recomputed_root = hashlib.sha256(
            f"{_prev_day_root(db, date)}|{date}|{len(revs)}|{joined}".encode("utf-8")).hexdigest()
        anchor_match = recomputed_root == anchor.root_hash
    return {
        "date": date,
        "links": len(revs),
        "broken_at": broken_at,
        "anchor_match": anchor_match,
        "anchor_root": anchor.root_hash if anchor else None,
        "recomputed_root": recomputed_root,
        "ok": broken_at is None and (anchor_match or not revs),
    }
