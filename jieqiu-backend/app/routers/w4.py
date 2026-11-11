"""W4 端点：公开账本（JSON + HTML）、链验证、锚点、SSE 叙述、模型评估。"""
from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DailyAnchor, ModelEval, SPMatch, Verdict
from ..modules.narrate import generate_stream
from ..modules.sealchain import verify_day
from ..modules.settle import ledger_stats

router = APIRouter()


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _ledger_rows(db: Session, limit: int):
    return db.scalars(
        select(Verdict).order_by(Verdict.trade_date.desc(), Verdict.kickoff)
        .limit(limit)
    ).all()


_LEDGER_CACHE: dict[str, tuple[float, object, object]] = {}
_LEDGER_TTL = 30.0


def _ledger_cached(db: Session, limit: int):
    """返回 (rows, stats)，30s 缓存；测试环境直读。"""
    import time
    from ..config import get_settings
    if get_settings().env == "test":
        rows = _ledger_rows(db, limit)
        return rows, ledger_stats(db)
    key = str(limit)
    now = time.time()
    hit = _LEDGER_CACHE.get(key)
    if hit and now - hit[0] < _LEDGER_TTL:
        return hit[1], hit[2]
    rows, stats = _ledger_rows(db, limit), ledger_stats(db)
    if len(_LEDGER_CACHE) > 50:
        _LEDGER_CACHE.clear()
    _LEDGER_CACHE[key] = (now, rows, stats)
    return rows, stats


@router.get("/api/ledger")
def ledger_api(limit: int = 100, db: Session = Depends(get_db)):
    """公开账本 JSON（F14）：全部判决 + 结算 + 连败公开。"""
    limit = max(1, min(limit, 500))
    rows, stats = _ledger_cached(db, limit)
    ids = {v.match_id for v in rows}
    matches = {m.match_id: m for m in db.scalars(
        select(SPMatch).where(SPMatch.match_id.in_(ids)))} if ids else {}
    items = []
    for v in rows:
        m = matches.get(v.match_id)
        items.append({
            "id": v.id,
            "trade_date": v.trade_date,
            "match_no": v.match_no,
            "match": f"{v.home} vs {v.away}",
            "league": m.league if m else (v.league or ""),
            "kickoff": v.kickoff,
            "pool": v.pool,
            "goal_line": v.goal_line,
            "pick": v.pick,
            "status": v.status,
            "settled": v.settled,
            "result_score": v.result_score,
            "hash": v.payload_hash,
            "seal_url": f"/verdicts/{v.id}/seal",
        })
    return {"items": items, "stats": stats}


@router.get("/ledger", response_class=HTMLResponse)
def ledger_page(db: Session = Depends(get_db)):
    """公开账本 Web 页（F14）：无样式依赖、可独立核验（每行带 seal 链接）。"""
    rows, stats = _ledger_cached(db, 200)
    trs = []
    for v in rows:
        settled_badge = {"win": "✓ 中", "lose": "✗ 未中"}.get(v.settled, "… 待定")
        color = {"win": "#0B6B4F", "lose": "#BE3A2B"}.get(v.settled, "#73787F")
        trs.append(
            f"<tr><td>{_esc(v.trade_date)}</td><td>{_esc(v.match_no)}</td>"
            f"<td>{_esc(v.home)} vs {_esc(v.away)}</td>"
            f"<td>{_esc(v.pool)}{(' ' + _esc(v.goal_line)) if v.goal_line else ''}</td>"
            f"<td>{_esc((v.pick or {}).get('dir', '—'))}</td>"
            f"<td>{_esc(v.status)}</td>"
            f"<td style='color:{color};font-weight:600'>{settled_badge}"
            f"{(' ' + _esc(v.result_score)) if v.result_score else ''}</td>"
            f"<td class='hash'>{_esc(v.payload_hash[:12])}…</td>"
            f"<td><a href='/verdicts/{_esc(v.id)}/seal'>验证</a></td></tr>"
        )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>球多多 · 公开账本</title>
<style>
body{{font-family:"PingFang SC",system-ui,sans-serif;max-width:960px;margin:0 auto;padding:24px;color:#1D2026;background:#F4F3EF}}
h1{{font-size:20px}} .stats{{display:flex;gap:18px;margin:12px 0 18px;font-size:13px;color:#73787F}}
.stats b{{color:#1D2026;font-family:ui-monospace,monospace}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;background:#fff;border-radius:12px;overflow:hidden}}
th,td{{padding:7px 9px;border-bottom:1px solid #E7E4DC;text-align:left}}
th{{background:#E9F3EE;color:#0B6B4F;font-weight:600}}
.hash{{font-family:ui-monospace,monospace;color:#73787F}}
a{{color:#0B6B4F}}
.note{{font-size:11px;color:#73787F;margin-top:14px;line-height:1.7}}
</style></head><body>
<h1>球多多 · 公开账本</h1>
<div class="stats">
<span>已推 <b>{stats['promoted_total']}</b></span>
<span>已结算 <b>{stats['settled']}</b></span>
<span>中 <b>{stats['wins']}</b></span>
<span>未中 <b>{stats['losses']}</b></span>
<span>当前连败 <b>{stats['current_losing_streak']}</b>（公开）</span>
</div>
<table><thead><tr><th>日期</th><th>编号</th><th>对阵</th><th>玩法</th><th>判断</th><th>状态</th><th>结算</th><th>封存哈希</th><th>核验</th></tr></thead>
<tbody>{''.join(trs) or '<tr><td colspan="9">暂无判决</td></tr>'}</tbody></table>
<p class="note">每条判断赛前封存：sha256(规范化 JSON)，任何人可独立复算（点「验证」获取原文与方法）。<br>
连败也公开 —— 我们不删历史。数据分析结果，不构成投注建议。</p>
</body></html>"""
    return HTMLResponse(html)


@router.get("/chain/verify")
def chain_verify(date: str | None = None, db: Session = Depends(get_db)):
    """独立复算某日链 + 锚根。date 缺省 = 最新锚点日。篡改 → broken_at 定位。"""
    d = date
    if not d:
        a = db.scalar(select(DailyAnchor).order_by(DailyAnchor.date.desc()).limit(1))
        if a is None:
            raise HTTPException(404, "no anchor yet")
        d = a.date
    return verify_day(db, d)


@router.get("/anchor/latest")
def anchor_latest(db: Session = Depends(get_db)):
    a = db.scalar(select(DailyAnchor).order_by(DailyAnchor.date.desc()).limit(1))
    if a is None:
        raise HTTPException(404, "no anchor yet")
    return _anchor_payload(db, a)


@router.get("/anchor/{date}")
def anchor_by_date(date: str, db: Session = Depends(get_db)):
    a = db.get(DailyAnchor, date)
    if a is None:
        raise HTTPException(404, "anchor not found")
    return _anchor_payload(db, a)


def _anchor_payload(db: Session, a: DailyAnchor) -> dict:
    """锚点 + 全部链节哈希：外部验证者可完全离线重算 root（F14 gate：独立核验 10/10）。"""
    from ..modules.sealchain import _day_revisions

    revs = _day_revisions(db, a.date)
    chain_hashes = [r.chain_hash for r in sorted(revs, key=lambda x: x.id)]
    return {
        "date": a.date,
        "root_hash": a.root_hash,
        "revision_count": a.revision_count,
        "prev_root": a.prev_root,
        "chain_hashes": chain_hashes,
        "built_at": a.built_at.isoformat(),
        "verify": f"/chain/verify?date={a.date}",
        "verify_hint": (
            "root = sha256(f'{prev_root}|{date}|{count}|{\"|\".join(chain_hashes)}') —— "
            "chain_hashes 本响应自带，可完全离线复算"
        ),
    }


@router.get("/verdicts/{verdict_id}/narration.stream")
def narration_stream(verdict_id: str, persona: str = "zhuanjia",
                     db: Session = Depends(get_db)):
    """SSE 流式叙述：结构数字不进模板变量之外的地方；任何失败走模板兜底（弱网 gate）。"""
    v = db.get(Verdict, verdict_id)
    if v is None:
        raise HTTPException(404, "verdict not found")
    if persona not in ("zhuanjia", "laopao", "meng"):
        persona = "zhuanjia"

    def gen():
        for kind, data in generate_stream(v, persona, db=db):
            if kind == "delta":
                yield f"data: {data}\n\n"
            else:
                yield f"event: done\ndata: {data}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@router.get("/model/evals", deprecated=True)
def model_evals(db: Session = Depends(get_db)):
    rows = db.scalars(select(ModelEval).order_by(ModelEval.run_at.desc()).limit(20)).all()
    return [{"id": r.id, "label": r.label, "run_at": r.run_at.isoformat(),
             "params": r.params, "metrics": r.metrics} for r in rows]
