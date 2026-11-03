"""editor_console（管理后台 · TechSpec §4.5 唯一自建界面）。

- 认证：控制台密码（JQ_CONSOLE_PASSWORD，默认 dev 时 "dev"）+ 可选 IP 白名单
- 页面：/console/login → /console（daily 日报）→ /console/alerts /variants /ops
- 数据：全部来自现有表聚合，不新增业务表
- 变体池（v1.5 编辑台骨架）：narrate 模板批量入池 → A(精选)/X(弃)/Q(排队) 状态机
"""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from ..config import get_settings
from ..db import get_db
from ..models import (DailyAnchor, MatchResult, ModelEval, SPSnapshot, User,
                      Verdict, VerdictRevision)
from ..modules.sealchain import latest_chain_status
from ..modules.settle import ledger_stats

router = APIRouter()

_SESSIONS: set[str] = set()  # 进程内会话（OPC 单实例；v1.5 换签名 cookie）


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _password_ok(pw: str) -> bool:
    real = os.environ.get("JQ_CONSOLE_PASSWORD") or ("dev" if get_settings().env != "prod" else "")
    if not real:
        return False  # prod 未设密码 → 拒绝（ fail closed）
    return hmac.compare_digest(pw, real)


def _ip_allowed(request: Request) -> bool:
    whitelist = os.environ.get("JQ_CONSOLE_IP_WHITELIST", "")
    if not whitelist:
        return True  # 未配置白名单 → 只靠密码
    ips = {x.strip() for x in whitelist.split(",") if x.strip()}
    return request.client.host in ips if request.client else False


def _authed(request: Request) -> bool:
    tok = request.query_params.get("t") or request.cookies.get("console_t")
    return bool(tok and tok in _SESSIONS)


def _deny() -> HTMLResponse:
    return RedirectResponse("/console/login", status_code=302)


def _page(title: str, body: str, tok: str = "") -> HTMLResponse:
    nav = (
        '<nav style="margin-bottom:16px;display:flex;gap:14px;font-size:13px">'
        '<a href="/console?t={t}">日报</a>'
        '<a href="/console/alerts?t={t}">告警</a>'
        '<a href="/console/variants?t={t}">变体池</a>'
        '<a href="/console/ops?t={t}">运维</a>'
        '<span style="color:#999">解球编辑台</span></nav>'
    ).format(t=tok)
    return HTMLResponse(
        f"<!DOCTYPE html><html lang=zh><head><meta charset=utf-8>"
        f"<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{title} · 解球编辑台</title><style>"
        "body{font-family:'PingFang SC',system-ui,sans-serif;max-width:960px;margin:0 auto;padding:24px;color:#1D2026;background:#F4F3EF}"
        "table{width:100%;border-collapse:collapse;font-size:12.5px;background:#fff;border-radius:12px;overflow:hidden}"
        "th,td{padding:7px 9px;border-bottom:1px solid #E7E4DC;text-align:left}"
        "th{background:#E9F3EE;color:#0B6B4F}h1{font-size:20px}h2{font-size:15px;margin-top:22px}"
        ".kv{display:flex;gap:18px;font-size:13px;margin:8px 0}.kv b{font-family:ui-monospace,monospace}"
        ".ok{color:#0B6B4F;font-weight:600}.bad{color:#BE3A2B;font-weight:600}.warn{color:#8A5A14}"
        "form.inline{display:inline}"
        "</style></head><body><h1>" + title + "</h1>" + nav + body + "</body></html>"
    )


# ---------- 登录 ----------

@router.get("/console/login", response_class=HTMLResponse)
def console_login_form(request: Request):
    if _authed(request):
        return RedirectResponse("/console", status_code=302)
    return _page("登录", """
<form method="post" action="/console/login" style="max-width:320px">
  <input type="password" name="pw" placeholder="控制台密码" style="width:100%;padding:9px;border:1px solid #ccc;border-radius:9px">
  <button style="margin-top:10px;width:100%;padding:9px;background:#0B6B4F;color:#fff;border:0;border-radius:9px;cursor:pointer">进入</button>
</form>""")


@router.post("/console/login")
def console_login(request: Request, pw: str = Form("")):
    if not _ip_allowed(request):
        return HTMLResponse("IP 不在白名单", status_code=403)
    if not _password_ok(pw):
        return _page("登录", '<p class="bad">密码错误</p>' + """
<form method="post" action="/console/login" style="max-width:320px">
  <input type="password" name="pw" placeholder="控制台密码" style="width:100%;padding:9px;border:1px solid #ccc;border-radius:9px">
  <button style="margin-top:10px;width:100%;padding:9px;background:#0B6B4F;color:#fff;border:0;border-radius:9px">进入</button>
</form>""")
    import secrets
    tok = secrets.token_urlsafe(24)
    _SESSIONS.add(tok)
    resp = RedirectResponse("/console?t=" + tok, status_code=302)
    resp.set_cookie("console_t", tok, httponly=True, max_age=86400)
    return resp


def _require(request: Request):
    if not _authed(request):
        raise HTTPException(status_code=302, detail="unauthorized",
                            headers={"Location": "/console/login"})


# ---------- 日报 ----------

@router.get("/console", response_class=HTMLResponse)
def console_daily(request: Request, db=Depends(get_db)):
    _require(request)
    tok = request.query_params.get("t") or request.cookies.get("console_t") or ""
    today = (_now() + timedelta(hours=8)).strftime("%Y-%m-%d")
    n_matches = db.scalar(select(func.count()).select_from(MatchResult)) or 0
    n_snaps = db.scalar(select(func.count()).select_from(SPSnapshot)) or 0
    n_verdicts = db.scalar(select(func.count()).select_from(Verdict)) or 0
    n_revisions = db.scalar(select(func.count()).select_from(VerdictRevision)) or 0
    n_users = db.scalar(select(func.count()).select_from(User)) or 0
    chain = latest_chain_status(db)
    anchor = db.scalar(select(DailyAnchor).order_by(DailyAnchor.date.desc()).limit(1))
    stats = ledger_stats(db)
    evals = db.scalars(select(ModelEval).order_by(ModelEval.run_at.desc()).limit(1)).all()
    last_eval = evals[0].metrics if evals else None
    last_snap = db.scalar(select(SPSnapshot.captured_at).order_by(SPSnapshot.captured_at.desc()).limit(1))

    body = f"""
<div class="kv"><span>比赛日</span><b>{today}</b></div>
<div class="kv"><span>竞彩场 / SP 快照</span><b>{db.scalar(select(func.count()).select_from(Verdict)) or 0} / {n_snaps}</b></div>
<div class="kv"><span>判决 / 修订链节</span><b>{n_verdicts} / {n_revisions}</b></div>
<div class="kv"><span>赛果库</span><b>{n_matches}</b> 场</div>
<div class="kv"><span>用户数</span><b>{n_users}</b></div>
<div class="kv"><span>最新快照</span><b>{last_snap or "—"}</b></div>
<h2>封存链</h2>
<div class="kv"><span>状态</span><b class="{'ok' if chain['ok'] else 'bad'}">{'OK · ' + str(chain['links']) + ' 节' if chain['ok'] else 'BROKEN @' + str(chain['broken_at'])}</b></div>
<div class="kv"><span>最新锚点</span><b>{(anchor.date + ' ' + anchor.root_hash[:16] + '…') if anchor else '—'}</b></div>
<h2>公开账本</h2>
<div class="kv"><span>已推 / 已结 / 中 / 连败</span><b>{stats['promoted_total']} / {stats['settled']} / {stats['wins']} / {stats['current_losing_streak']}</b></div>
<h2>模型最近评估</h2>
<div class="kv"><span>{('logloss ' + str(last_eval['logloss']) + ' · acc ' + str(last_eval['accuracy'])) if last_eval else '—'}</span></div>
<h2>近期判决</h2>
<table><tr><th>编号</th><th>对阵</th><th>状态</th><th>抽水</th><th>结算</th><th>哈希</th></tr>
{"".join(f"<tr><td>{v.match_no}</td><td>{v.home} vs {v.away}</td><td>{v.status}</td><td>{v.rake*100:.1f}%</td><td>{v.settled or '—'}</td><td>{v.payload_hash[:10]}…</td></tr>" for v in db.scalars(select(Verdict).order_by(Verdict.trade_date.desc()).limit(10)))}
</table>"""
    return _page("数据日报", body, tok)


# ---------- 告警 ----------

@router.get("/console/alerts", response_class=HTMLResponse)
def console_alerts(request: Request, db=Depends(get_db)):
    _require(request)
    tok = request.query_params.get("t") or request.cookies.get("console_t") or ""
    chain = latest_chain_status(db)
    alerts = []
    if not chain["ok"]:
        alerts.append(("严重", f"封存链断裂 @ 第 {chain['broken_at']} 节 —— 立即排查", "bad"))
    last_snap = db.scalar(select(SPSnapshot.captured_at).order_by(SPSnapshot.captured_at.desc()).limit(1))
    if last_snap:
        last_dt = datetime.strptime(last_snap[:19], "%Y-%m-%dT%H:%M:%S")
        lag_min = ((_now() + timedelta(hours=8)) - last_dt.replace(tzinfo=timezone(timedelta(hours=8)))).total_seconds() / 60
        if lag_min > 35:
            alerts.append(("严重" if lag_min > 90 else "警告",
                           f"采集同步延迟 {lag_min:.0f} 分钟（阈值 35）—— 检查本机采集器/家宽出口", "bad" if lag_min > 90 else "warn"))
    else:
        alerts.append(("严重", "无任何 SP 快照 —— 采集管道未运行", "bad"))
    st = get_settings()
    if not st.odds_api_key:
        alerts.append(("提示", "the-odds-api key 未配置 —— 市闸单源 pending", "warn"))
    if not os.environ.get("JQ_CONSOLE_PASSWORD"):
        alerts.append(("警告", "控制台密码未设置（当前仅 dev 环境可用）", "warn"))
    stale = db.scalar(select(func.count()).select_from(Verdict).where(
        Verdict.status == "screening")) or 0
    body = ("<table><tr><th>级别</th><th>内容</th></tr>" +
            ("".join(f"<tr><td class='{cls}'>{lv}</td><td>{c}</td></tr>" for lv, c, cls in alerts)
             or "<tr><td class='ok'>OK</td><td>无告警</td></tr>") + "</table>" +
            f'<div class="kv" style="margin-top:14px"><span>screening 存量</span><b>{stale}</b></div>')
    return _page("告警", body, tok)


# ---------- 变体池（v1.5 编辑台骨架） ----------

# 进程内状态：verdict_id -> {persona: A/X/Q/""}（v1.5 换 narrative_pool 表持久化）
_VARIANT_POOL: dict[str, dict[str, str]] = {}

PERSONAS = ("zhuanjia", "laopao", "meng")


@router.get("/console/variants", response_class=HTMLResponse)
def console_variants(request: Request, db=Depends(get_db)):
    _require(request)
    tok = request.query_params.get("t") or request.cookies.get("console_t") or ""
    from ..modules.narrate import build_narration
    rows = db.scalars(select(Verdict).order_by(Verdict.created_at.desc()).limit(5)).all()
    out = []
    for v in rows:
        st = _VARIANT_POOL.setdefault(v.id, {p: "" for p in PERSONAS})
        cards = []
        for p in PERSONAS:
            text, tid = build_narration(v, p)
            mark = st.get(p, "")
            btns = "".join(
                f'<form class="inline" method="post" action="/console/variants?v={v.id}&p={p}&m={m}&t={tok}">'
                f'<button style="{"font-weight:700" if mark == m else ""};cursor:pointer;border:1px solid #ccc;background:'
                f'{"#E9F3EE" if mark == m else "#fff"};border-radius:6px;padding:2px 8px">{m}</button></form>'
                for m in ("A", "Q", "X"))
            cards.append(f"<div style='margin:6px 0'><b>{p}</b> {btns}<br>"
                         f"<span style='color:#555;font-size:12px'>{text}</span></div>")
        out.append(f"<div style='background:#fff;border:1px solid #E7E4DC;border-radius:12px;padding:12px;margin:10px 0'>"
                   f"<b>{v.match_no} {v.home} vs {v.away}</b>（{v.status}）" + "".join(cards) + "</div>")
    body = ("<div class='meta' style='font-size:12px;color:#73787F;margin-bottom:8px'>"
            "A=入选投放 · Q=排队 · X=弃。v1.5 换 narrative_pool 表持久化（当前进程内存）。</div>" +
            ("".join(out) or "<p>今日暂无判决</p>"))
    return _page("变体池", body, tok)


@router.post("/console/variants")
def console_variants_mark(request: Request, v: str = "", p: str = "", m: str = "",
                          t: str = "", db=Depends(get_db)):
    _require(request)
    if v and p in PERSONAS and m in ("A", "Q", "X"):
        _VARIANT_POOL.setdefault(v, {})[p] = m
    return RedirectResponse(f"/console/variants?t={t}", status_code=302)


# ---------- 快捷运维 ----------

@router.get("/console/ops", response_class=HTMLResponse)
def console_ops(request: Request, db=Depends(get_db)):
    _require(request)
    tok = request.query_params.get("t") or request.cookies.get("console_t") or ""
    h = get_settings().env
    odds_state = "the-odds-api 已配" if (os.environ.get("ODDS_API_KEY") or get_settings().odds_api_key) else "the-odds-api 未配"
    body = f"""
<div class="kv"><span>环境</span><b>{h}</b></div>
<div class="kv"><span>数据源</span><b>sporttery · {odds_state}</b></div>
<h2>cron 日志尾部（服务器上查看）</h2>
<pre style="background:#fff;border:1px solid #E7E4DC;border-radius:9px;padding:10px;font-size:11.5px">ssh: tail -20 /home/ubuntu/jieqiu-backend/sync.log
ssh: tail -20 /home/ubuntu/jieqiu-backend/backtest.log
ssh: tail -20 /home/ubuntu/jieqiu-backend/purge.log</pre>
<h2>快捷动作（v1.5 接作业队列；当前给命令）</h2>
<pre style="background:#fff;border:1px solid #E7E4DC;border-radius:9px;padding:10px;font-size:11.5px">重跑判决：python -m app.seed /home/ubuntu/jieqiu-sp/sp_data.db
跑回测：  python -m app.backtest_cli
清注销：  python -m app.purge_cli
验链：    curl -s '/chain/verify?date=今天'</pre>"""
    return _page("运维", body, tok)
