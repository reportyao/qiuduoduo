"""运营工作台：把采集→入库→市场→模型→三闸→封存→复核→发布→LLM→推送
串成一条可读的链，而不是让运营在多个页面之间猜。

只做读取与诊断；动作走独立 allowlist，不执行任意命令。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import (AIAnalysis, AIResearch, CollectorStatus, DecisionSnapshot,
                       ModelRun, PushToken, RecommendationPlan, ReviewRun,
                       SPMatch, SPSnapshot, SportmonksMatchData, Verdict)
from ...modules import api_football, llm_gateway
from ...modules.sealchain import latest_chain_status
from ...modules.supply import content_supply
from ...modules.timeutil import CN, trade_date_now, trade_window

_DEFINITIONS = {
    "SP": "竞彩官方开出的胜平负/让球赔率快照。采集器每 5 分钟抓一次，服务器上的 sp_data.db 是原始数据。",
    "主链": "从采集到前端展示的完整流水线：采集 → 入库 → 模型 → 三闸 → 封存 → 复核 → 发布。",
    "三闸": "价闸（抽水是否过高）、市闸（竞彩官方与国际盘是否对得上）、模闸（模型是否有足够数据）。三闸全过才可能 promoted。",
    "封存": "把判决内容做哈希写入链，事后任何人可复算；封存不等于发布。",
    "复核": "L1–L5 规则复核 + 可选 LLM 语义复核；复核通过后才允许发布。",
    "published": "只有复核通过且发布后的内容才会出现在前端「今日预测」；promoted 只是通过三关。",
    "deep_eligible": "单场 AI 解读的资格：价、市、模齐全，且阵容已出或距开赛足够久。",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _age(seconds: int | None) -> str:
    if seconds is None:
        return "未知"
    if seconds < 60:
        return f"{max(0, seconds)} 秒"
    if seconds < 3600:
        return f"{seconds // 60} 分钟"
    return f"{seconds / 3600:.1f} 小时"


def _state(ok: bool, warn: bool = False) -> str:
    return "ok" if ok else "warn" if warn else "blocked"


def _stage(key: str, title: str, question: str, definition: str,
           state: str, headline: str, metrics: list[dict],
           evidence: list[str] | str, next_step: str,
           actions: list[str] | None = None) -> dict:
    # 前端按数组渲染 evidence；这里兜底，避免单个阶段参数写错把整页打挂。
    if isinstance(evidence, str):
        evidence = [evidence] if evidence else []
    return {"key": key, "title": title, "question": question,
            "definition": definition, "state": state, "headline": headline,
            "metrics": metrics, "evidence": evidence, "next": next_step,
            "actions": actions or []}


def _collector(db: Session) -> dict:
    row = db.get(CollectorStatus, 1)
    now = _utcnow()
    data_path = get_settings().collector_data_path
    data_age = None
    try:
        mtime = datetime.fromtimestamp(
            Path(data_path).stat().st_mtime, timezone.utc).replace(tzinfo=None)
        data_age = int((now - mtime).total_seconds())
    except OSError:
        pass
    stale = int((now - row.last_seen).total_seconds()) if row and row.last_seen else None
    online = stale is not None and stale <= 600
    return {"row": row, "online": online, "stale_seconds": stale,
            "data_age_seconds": data_age}


def build_workbench(db: Session, date: str | None = None) -> dict:
    date = date or trade_date_now()
    start, end = trade_window(date)
    supply = content_supply(db, date)
    collector = _collector(db)
    af = api_football.status(db)
    chain = latest_chain_status(db)
    matches = list(db.scalars(select(SPMatch).where(
        SPMatch.kickoff >= start, SPMatch.kickoff <= end)).all())
    no_matches = len(matches) == 0
    next_match = db.scalar(select(SPMatch).where(
        SPMatch.kickoff > end).order_by(SPMatch.kickoff).limit(1)) if no_matches else None
    match_ids = [m.match_id for m in matches]
    snapshots_total = int(db.scalar(select(func.count()).select_from(SPSnapshot).where(
        SPSnapshot.match_id.in_(match_ids))) or 0) if match_ids else 0
    # 采集阶段看“今天抓到的快照”，历史快照不能冒充今天的采集健康。
    snapshots_today = int(db.scalar(select(func.count()).select_from(SPSnapshot).where(
        SPSnapshot.match_id.in_(match_ids),
        SPSnapshot.captured_at.like(f"{date}%"))) or 0) if match_ids else 0
    missing_league = sum(1 for m in matches if not (m.league or "").strip())
    verdicts = list(db.scalars(select(Verdict).where(
        Verdict.trade_date == date)).all())
    sealed = sum(1 for v in verdicts if v.sealed_at is not None)
    promoted = sum(1 for v in verdicts if v.status == "promoted")
    model_runs = int(db.scalar(select(func.count()).select_from(ModelRun).where(
        ModelRun.run_date == date)) or 0)
    snaps = list(db.scalars(select(DecisionSnapshot).where(
        DecisionSnapshot.trade_date == date)).all())
    plans = list(db.scalars(select(RecommendationPlan).where(
        RecommendationPlan.trade_date == date)).all())
    review_runs = list(db.scalars(select(ReviewRun).where(
        ReviewRun.created_at >= datetime.now(CN).replace(tzinfo=None)
        - timedelta(days=1))).all())
    analyses = int(db.scalar(select(func.count()).select_from(AIAnalysis).where(
        AIAnalysis.trade_date == date)) or 0)
    profiles = llm_gateway.profile_status(db)
    fast = next((p for p in profiles if p["name"] == "fast"), {})
    deep = next((p for p in profiles if p["name"] == "deep"), {})
    usage = llm_gateway.usage_summary(db, day=date)
    recent_errors = [u for u in usage.get("recent", []) if u.get("status") != "ok"]
    tokens_total = int(db.scalar(select(func.count()).select_from(PushToken)) or 0)
    tokens_enabled = int(db.scalar(select(func.count()).select_from(PushToken).where(
        PushToken.enabled.is_(True))) or 0)

    stages = []

    # 1 采集
    # 采集器每 30 分钟 SFTP 推一次文件；心跳 10 分钟。文件 35 分钟内更新都算正常。
    c_ok = bool(collector["online"] and
                (no_matches or (collector["data_age_seconds"] or 10**9) <= 2100))
    c_warn = c_ok and not no_matches and (snapshots_today == 0 or missing_league > 0)
    stages.append(_stage(
        "collect", "采集", "今天有没有拿到官方 SP？", _DEFINITIONS["SP"],
        _state(c_ok, c_warn),
        f"采集器{'在线' if collector['online'] else '离线'}，SP 文件 {_age(collector['data_age_seconds'])}前更新",
        [
            {"label": "采集器心跳", "value": "在线" if collector["online"] else "离线"},
            {"label": "心跳年龄", "value": _age(collector["stale_seconds"])},
            {"label": "SP 文件年龄", "value": _age(collector["data_age_seconds"])},
            {"label": "今日快照", "value": str(snapshots_today)},
            {"label": "历史快照", "value": str(snapshots_total)},
        ],
        [f"比赛 {len(matches)} 场，其中 {missing_league} 场联赛字段为空"
         if missing_league else f"比赛 {len(matches)} 场"],
        ("检查采集器网络" if collector["online"] else "启动采集器")
        if not c_ok else ("补齐联赛字段" if missing_league else "正常"),
        ["restart_collector"] if not c_ok else [],
    ))

    # 2 入库
    ingest_ok = no_matches or (len(matches) > 0 and snapshots_today > 0)
    stages.append(_stage(
        "ingest", "入库", "采集数据有没有正确进入后端？",
        "采集器推送 sp_data.db 后，seed 把场次和 SP 快照写入后端数据库。",
        _state(ingest_ok, ingest_ok and not no_matches and missing_league > 0),
        "当前销售日无在售场次" if no_matches else f"{len(matches)} 场已入库，今日 {snapshots_today} 条 SP 快照",
        [{"label": "场次", "value": str(len(matches))},
         {"label": "今日 SP 快照", "value": str(snapshots_today)},
         {"label": "空联赛", "value": str(missing_league)}],
        ["seed 每 30 分钟运行一次"],
        "检查 seed/cron" if not ingest_ok else "正常",
    ))

    # 3 情报：Sportmonks 预测/市场 + AI 情报
    if match_ids:
        sm_count = int(db.scalar(select(func.count()).select_from(SportmonksMatchData).where(
            SportmonksMatchData.match_id.in_(match_ids))) or 0)
        intel_ready = int(db.scalar(select(func.count()).select_from(AIResearch).where(
            AIResearch.match_id.in_(match_ids), AIResearch.status == "ready")) or 0)
    else:
        sm_count = intel_ready = 0
    info_ok = no_matches or (sm_count == len(matches) and intel_ready == len(matches))
    info_warn = (not no_matches) and (sm_count > 0 or intel_ready > 0)
    stages.append(_stage(
        "intel", "情报", "Sportmonks 预测/市场和 AI 情报是否齐全？",
        "Sportmonks 提供 1X2 预测与 Pinnacle 市场；AI 情报是公开事实的中文摘要，不是概率。",
        "idle" if no_matches else _state(info_ok, info_warn),
        (f"Sportmonks 覆盖 {sm_count}/{len(matches)} 场，AI 情报就绪 {intel_ready}/{len(matches)} 场"
         if not no_matches else "无在售场次，情报同步待下一销售日"),
        [
            {"label": "Sportmonks 覆盖", "value": f"{sm_count}/{len(matches)}"},
            {"label": "AI 情报就绪", "value": f"{intel_ready}/{len(matches)}"},
        ],
        ([f"Sportmonks 覆盖 {sm_count}/{len(matches)} 场",
          f"AI 情报就绪 {intel_ready}/{len(matches)} 场"]
         if not no_matches else ["无在售场次，情报同步待下一销售日"]),
        "同步 Sportmonks" if sm_count < len(matches) else ("同步 AI 情报" if intel_ready < len(matches) else "正常"),
        (["sync_sportmonks"] if sm_count < len(matches) else [])
        + (["sync_intel"] if intel_ready < len(matches) else []),
    ))

    # 4 市场
    intl = supply["intl_odds"]
    sm_market = supply.get("sportmonks_market", {})
    cover = supply.get("market_covered_matches", intl["covered_matches"])
    total = supply["matches"]
    market_ok = no_matches or cover > 0
    stages.append(_stage(
        "market", "市场数据", "Sportmonks 市场与国际盘够不够？",
        "市闸需要竞彩官方 + 至少一条市场源（Sportmonks Pinnacle 或国际盘）；API-Football 只补阵容、伤停。",
        _state(market_ok, market_ok and not no_matches and cover < total),
        ("当前销售日无在售场次，不需要请求市场数据" if no_matches else
         f"市场覆盖 {cover}/{total} 场（Sportmonks {sm_market.get('covered_matches', 0)} · 国际盘 {intl['covered_matches']}）；API-Football 今日已用 {af.get('used_today', 0)}/{af.get('daily_limit', 0)} 次"),
        [{"label": "市场覆盖", "value": f"{cover}/{total}"},
         {"label": "SM Pinnacle", "value": str(sm_market.get("covered_matches", 0))},
         {"label": "今日国际盘", "value": str(intl["total"])},
         {"label": "阵容行", "value": str(af.get("target", {}).get("lineups", 0))},
         {"label": "伤停", "value": str(af.get("target", {}).get("injuries", 0))}],
        [intl.get("configured") and "Odds API 已配置" or "Odds API 未配置",
         "API-Football 积分榜当前关闭" if not af.get("standings_enabled") else "积分榜开启"],
        "补齐 Sportmonks 映射/赔率" if not market_ok else ("覆盖仍不完整" if cover < total else "正常"),
        (["sync_sportmonks"] if sm_market.get("covered_matches", 0) < total else [])
        + (["sync_odds"] if intl["covered_matches"] < total else []),
    ))

    # 5 模型
    v_status = supply["verdicts"]
    model_ok = no_matches or (v_status["total"] > 0 and model_runs > 0)
    stages.append(_stage(
        "model", "模型", "模型有没有算出可用的概率？",
        "确定性统计模型生成胜平负概率；模型闸检查覆盖率，不把 LLM 当预测器。",
        _state(model_ok, model_ok and not no_matches and v_status["promoted"] == 0),
        "当前销售日无在售场次" if no_matches else f"今日 {v_status['total']} 条判决，{v_status['promoted']} 条通过三关，模型运行 {model_runs} 次",
        [{"label": "判决", "value": str(v_status["total"])},
         {"label": "promoted", "value": str(v_status["promoted"])},
         {"label": "模型运行", "value": str(model_runs)}],
        ["模型输出不是承诺，概率必须带区间/校准口径"],
        "正常" if model_ok else "检查 build_verdicts/model",
    ))

    # 6 三闸
    gates = supply["market_gate"]
    price_pass = sum(1 for v in verdicts
                     if (v.gates or {}).get("price", {}).get("result") == "pass")
    model_pass = sum(1 for v in verdicts
                     if (v.gates or {}).get("model", {}).get("result") == "pass")
    gates_ok = no_matches or (bool(verdicts) and promoted > 0)
    stages.append(_stage(
        "gates", "三闸", "价 / 市 / 模分别卡在哪？", _DEFINITIONS["三闸"],
        _state(gates_ok, bool(verdicts) and not gates_ok),
        "当前销售日无在售场次" if no_matches else f"价闸过 {price_pass}，市闸过 {gates.get('pass', 0)}，模闸过 {model_pass}；promoted {promoted}",
        [{"label": "价闸", "value": f"{price_pass}/{len(verdicts)}"},
         {"label": "市闸", "value": f"{gates.get('pass', 0)} 过 / {gates.get('pending_data', 0)} 待"},
         {"label": "模闸", "value": f"{model_pass}/{len(verdicts)}"}],
        ["三闸全过只是 promoted，不等于已发布"],
        "先补市场/模型数据" if not gates_ok else "正常",
    ))

    # 7 封存
    stages.append(_stage(
        "seal", "封存", "判决有没有写入不可篡改链？", _DEFINITIONS["封存"],
        _state(no_matches or (bool(chain.get("ok")) and sealed > 0),
               bool(chain.get("ok")) and sealed == 0),
        "当前销售日无在售场次，无封存" if no_matches else f"链 {'正常' if chain.get('ok') else '异常'}，本日已封存 {sealed}/{len(verdicts)}",
        [{"label": "链状态", "value": "正常" if chain.get("ok") else "断裂"},
         {"label": "链接数", "value": str(chain.get("links", 0))},
         {"label": "已封存", "value": str(sealed)}],
        [f"锚点日 {chain.get('date')}"],
        "检查封存链" if not chain.get("ok") else "正常",
    ))

    # 8 复核
    failed_snaps = sum(1 for s in snaps if s.status == "review_failed")
    failed_plans = sum(1 for p in plans if p.status == "review_failed")
    passed_runs = sum(1 for r in review_runs if r.status == "passed")
    degraded_runs = sum(1 for r in review_runs if r.llm_degraded)
    review_ok = not (failed_snaps or failed_plans)
    stages.append(_stage(
        "review", "复核", "AI 复核有没有跑、有没有降级？", _DEFINITIONS["复核"],
        _state(review_ok, degraded_runs > 0),
        f"近 24h 复核 {len(review_runs)} 次，通过 {passed_runs}，失败 {failed_snaps + failed_plans}，LLM 降级 {degraded_runs}",
        [{"label": "复核运行", "value": str(len(review_runs))},
         {"label": "复核失败", "value": str(failed_snaps + failed_plans)},
         {"label": "LLM 降级", "value": str(degraded_runs)}],
        ["AI 复核是可选增强；降级时规则门仍可能通过"],
        "检查复核失败层" if not review_ok else "正常",
    ))

    # 9 发布
    published = supply["published"]
    stages.append(_stage(
        "publish", "发布", "前端今天能看到几条？", _DEFINITIONS["published"],
        _state(no_matches or published > 0, bool(snaps or plans) and published == 0),
        "当前销售日无在售场次" if no_matches else f"已发布 {published} 条；snapshot {supply['snapshots']['published']}，plan {supply['plans']['published']}",
        [{"label": "已发布", "value": str(published)},
         {"label": "snapshot", "value": f"{supply['snapshots']['published']}/{supply['snapshots']['total']}"},
         {"label": "plan", "value": f"{supply['plans']['published']}/{supply['plans']['total']}"}],
        [supply.get("blocked_reason") or "无阻塞"],
        "发布门未通过" if published == 0 else "正常",
        ["run_pipeline"] if published == 0 and promoted > 0 else [],
    ))

    # 10 LLM
    llm_ok = bool(fast.get("configured") and deep.get("configured"))
    stages.append(_stage(
        "llm", "LLM", "对话/复核/解读是否可用？",
        "fast 服务对话与轻任务，deep 服务发布复核与单场解读；两者都来自接入中心或环境变量。",
        _state(llm_ok, degraded_runs > 0),
        f"fast {'已配' if fast.get('configured') else '未配'}（{fast.get('model', '—')}）；deep {'已配' if deep.get('configured') else '未配'}（{deep.get('model', '—')}）；今日解读 {analyses} 条",
        [{"label": "fast", "value": fast.get("model", "—")},
         {"label": "deep", "value": deep.get("model", "—")},
         {"label": "AI 解读", "value": str(analyses)},
         {"label": "最近错误", "value": str(len(recent_errors))}],
        [u.get("error_class") or "" for u in recent_errors[:3] if u.get("error_class")],
        "在接入中心测试/补 Key" if not llm_ok else "正常",
        ["test_llm"] if not llm_ok else [],
    ))

    # 11 推送
    push_ok = tokens_enabled > 0
    stages.append(_stage(
        "push", "推送", "设备推送有没有绑定？",
        "JPush 负责通知；服务端未配 Master Secret 时只 dry-run，不影响主链。",
        _state(push_ok, tokens_total > 0 and tokens_enabled == 0),
        f"已启用设备 {tokens_enabled}/{tokens_total}",
        [{"label": "启用 token", "value": str(tokens_enabled)},
         {"label": "总 token", "value": str(tokens_total)}],
        ["推送不是预测发布的前置条件"],
        "检查 JPush/设备注册" if not push_ok else "正常",
    ))

    blocked = [s for s in stages if s["state"] == "blocked"]
    warn = [s for s in stages if s["state"] == "warn"]
    headline = (f"今日 {len(matches)} 场 · SP {snapshots_today} 条 · "
                f"国际盘 {cover}/{len(matches)} · 已发布 {published}")
    if no_matches:
        nxt = (f"下一场 {next_match.home} vs {next_match.away}（{next_match.kickoff}）"
               if next_match is not None else "暂无下一批赛程")
        headline = f"{date} 销售日无在售场次；{nxt}"
    elif blocked:
        headline += f"；主卡点：{blocked[0]['title']}"
    elif warn:
        headline += f"；需关注：{warn[0]['title']}"
    else:
        headline += "；主链正常"
    return {
        "date": date,
        "generated_at": datetime.now(CN).isoformat(timespec="seconds"),
        "headline": headline,
        "overall": ("blocked" if blocked else "warn" if warn else
                    "idle" if no_matches else "ok"),
        "stages": stages,
        "blockers": [{"key": s["key"], "title": s["title"],
                      "headline": s["headline"], "next": s["next"]}
                     for s in blocked],
        "warnings": [{"key": s["key"], "title": s["title"],
                      "headline": s["headline"]} for s in warn],
        "definitions": _DEFINITIONS,
        "raw": {
            "collector": {"online": collector["online"],
                          "stale_seconds": collector["stale_seconds"],
                          "data_age_seconds": collector["data_age_seconds"],
                          "last_error": collector["row"].last_error if collector["row"] else ""},
            "supply": supply,
            "api_football": af,
            "chain": chain,
            "promoted": promoted,
            "published": published,
            "model_runs": model_runs,
            "snapshots_today": snapshots_today,
            "snapshots_total": snapshots_total,
            "analyses": analyses,
            "llm": {"fast": fast, "deep": deep, "recent_errors": recent_errors[:5]},
            "push": {"total": tokens_total, "enabled": tokens_enabled},
            "missing_league": missing_league,
            "no_matches": no_matches,
            "next_match": ({"home": next_match.home, "away": next_match.away,
                            "kickoff": next_match.kickoff} if next_match else None),
        },
    }


_ACTIONS = {
    "restart_collector": {"label": "重启采集器", "safe": True},
    "sync_odds": {"label": "同步国际盘", "safe": False},
    "sync_sportmonks": {"label": "同步 Sportmonks", "safe": False},
    "sync_intel": {"label": "同步 AI 情报", "safe": False},
    "test_llm": {"label": "测试 LLM", "safe": True},
    "run_pipeline": {"label": "运行主链", "safe": False},
}


def _action_items(ids: list[str]) -> list[dict]:
    out = []
    for action_id in ids:
        meta = _ACTIONS.get(action_id)
        if meta:
            out.append({"id": action_id, **meta})
    return out


def _fallback_diagnosis(wb: dict) -> dict:
    if (wb.get("raw") or {}).get("no_matches"):
        nxt = (wb.get("raw") or {}).get("next_match") or {}
        tip = (f"当前销售日没有在售场次；下一场 {nxt.get('home')} vs {nxt.get('away')}"
               f"（{nxt.get('kickoff')}）。" if nxt else "当前销售日没有在售场次，暂无下一批赛程。")
        return {"headline": wb.get("headline", ""), "root_causes": [],
                "actions": [], "needs_human": tip, "fallback": True}
    source = (wb.get("blockers") or wb.get("warnings") or [{}])[0]
    stage = next((s for s in wb.get("stages", [])
                  if s.get("key") == source.get("key")), {})
    return {
        "headline": wb.get("headline", "工作台快照"),
        "root_causes": [{
            "stage": stage.get("key", ""),
            "title": stage.get("title", ""),
            "why": stage.get("headline", ""),
            "evidence": stage.get("evidence", []),
        }] if stage else [],
        "actions": _action_items(stage.get("actions", [])),
        "needs_human": stage.get("next", "按阶段提示处理") if stage else "",
        "fallback": True,
    }


def diagnose_workbench(db: Session, date: str | None = None) -> dict:
    wb = build_workbench(db, date)
    if not (get_settings().llm_fast_api_key or db_profile_key(db, "fast")):
        return {**wb, "diagnosis": _fallback_diagnosis(wb)}
    compact = {
        "headline": wb["headline"],
        "stages": [{"key": s["key"], "title": s["title"], "state": s["state"],
                    "headline": s["headline"], "next": s["next"],
                    "metrics": s["metrics"]} for s in wb["stages"]],
        "blockers": wb["blockers"], "warnings": wb["warnings"],
        "raw": {
            "collector": wb["raw"]["collector"],
            "api_football": {k: wb["raw"]["api_football"].get(k) for k in
                             ("used_today", "daily_limit", "remaining",
                              "lineups", "injuries", "standings", "warnings")},
            "chain": wb["raw"]["chain"],
            "promoted": wb["raw"]["promoted"],
            "published": wb["raw"]["published"],
            "model_runs": wb["raw"]["model_runs"],
            "analyses": wb["raw"]["analyses"],
            "llm": wb["raw"]["llm"],
            "missing_league": wb["raw"]["missing_league"],
        },
    }
    result = llm_gateway.complete(
        db, "workbench_diagnose",
        [{"role": "system", "content": (
            "你是球多多运营工作台诊断器。只能依据给定 snapshot 判断，不得编造。"
            "找出最先阻塞的环节、证据和下一步；可建议动作 ID：restart_collector / "
            "sync_odds / test_llm / run_pipeline。涉及发布或花费额度的动作标记 safe=false。"
            "只输出 JSON。")},
         {"role": "user", "content": json.dumps(compact, ensure_ascii=False,
                                                sort_keys=True)[:12000]}],
        schema={
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "root_causes": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"stage": {"type": "string"},
                                   "title": {"type": "string"},
                                   "why": {"type": "string"},
                                   "evidence": {"type": "array", "items": {"type": "string"}}},
                }},
                "actions": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"},
                                   "label": {"type": "string"},
                                   "why": {"type": "string"},
                                   "safe": {"type": "boolean"}},
                }},
                "needs_human": {"type": "string"},
            },
            "required": ["headline", "root_causes", "actions", "needs_human"],
        },
        max_tokens=2400, temperature=0.1, timeout_s=90,
    )
    if result.degraded or not result.data:
        diagnosis = _fallback_diagnosis(wb)
    else:
        data = result.data
        valid = []
        for item in data.get("actions") or []:
            action_id = str(item.get("id") or "")
            if action_id not in _ACTIONS:
                continue
            valid.append({"id": action_id, "label": _ACTIONS[action_id]["label"],
                          "why": str(item.get("why") or "")[:200],
                          "safe": bool(item.get("safe", _ACTIONS[action_id]["safe"]))})
        causes = []
        for item in (data.get("root_causes") or [])[:5]:
            if isinstance(item, dict):
                causes.append({
                    "stage": str(item.get("stage") or ""),
                    "title": str(item.get("title") or "AI 诊断")[:80],
                    "why": str(item.get("why") or "")[:300],
                    "evidence": [str(e)[:160] for e in (item.get("evidence") or [])][:4],
                })
            elif str(item).strip():
                causes.append({"stage": "", "title": "AI 诊断",
                               "why": str(item)[:300], "evidence": []})
        fallback = _fallback_diagnosis(wb)
        diagnosis = {
            # 标题永远用确定性快照，避免模型把“采集”误报成卡点。
            "headline": wb["headline"],
            "root_causes": causes or fallback["root_causes"],
            "actions": valid or fallback["actions"],
            "needs_human": (str(data.get("needs_human") or "").strip()
                            or fallback["needs_human"]),
            "fallback": not (causes or valid),
        }
    return {**wb, "diagnosis": diagnosis}


def db_profile_key(db: Session, name: str) -> bool:
    return bool(llm_gateway._profile(name, db).get("api_key"))


def run_action(db: Session, action: str, date: str | None = None) -> dict:
    """执行 allowlist 动作；不执行任意 shell。"""
    date = date or trade_date_now()
    if action == "restart_collector":
        row = db.get(CollectorStatus, 1)
        if row is None:
            return {"ok": False, "message": "采集器从未上报心跳，无法下发重启"}
        row.restart_requested_at = _utcnow()
        db.commit()
        return {"ok": True, "message": "已下发重启；采集器下一次心跳会退出并由 watchdog 拉起"}
    if action == "sync_odds":
        from ...modules.align import Aligner
        from ...modules.intl_odds import sports_for_trade_date, sync_the_odds_api
        sports = sports_for_trade_date(db, date)
        n, note = sync_the_odds_api(
            db, Aligner(db), datetime.now(timezone.utc), sports=sports,
            trade_date=date)
        return {"ok": n > 0, "message": note, "synced": n, "sports": sports}
    if action == "sync_sportmonks":
        from ...modules.sportmonks import sync_trade_date as sync_sm
        result = sync_sm(db, date)
        return {"ok": bool(result.get("ok")),
                "message": f"Sportmonks 同步 {result.get('synced', 0)}/{result.get('matches', 0)} 场",
                **result}
    if action == "sync_intel":
        from ...modules.intel_research import sync_trade_date as sync_intel
        result = sync_intel(db, date)
        return {"ok": bool(result.get("ok")),
                "message": f"AI 情报同步 {result.get('synced', 0)}/{result.get('matches', 0)} 场",
                **result}
    if action == "test_llm":
        results = []
        for name in ("fast", "deep"):
            profile = llm_gateway._profile(name, db)
            if not profile.get("api_key") or not profile.get("enabled", True):
                results.append({"profile": name, "ok": False,
                                "error": "未配置或已停用"})
                continue
            try:
                text, usage = llm_gateway.call_profile(
                    profile, [{"role": "user", "content": "只回复：正常"}],
                    max_tokens=400, temperature=0, timeout_s=45)
                results.append({"profile": name, "model": profile["model"],
                                "ok": bool((text or "").strip()),
                                "text": (text or "").strip()[:80]})
            except Exception as exc:  # noqa: BLE001 - 返回给后台展示
                results.append({"profile": name, "ok": False,
                                "error": str(exc)[:160]})
        return {"ok": all(r.get("ok") for r in results), "results": results}
    if action == "run_pipeline":
        from ..recommendations import service as recommendation_service
        result = recommendation_service.run_pipeline(db, date=date, actor="admin-workbench")
        return {"ok": True, "message": "主链已运行", **result}
    return {"ok": False, "message": "未知动作"}
