"""判决模块 v3（W3 三道闸引擎）。

流程（每比赛日，幂等）：
  1) 取窗口内未开赛场次 + 各池最新 SP（SQL 聚合）
  2) 第一阶段：算全部候选场的抽水 → 动态阈值（当日中位数 + 3pp，夹 [10%,13%]）
  3) 第二阶段：逐场过三关
     价  抽水 ≤ 动态阈值
     市  竞彩去水 ⊕ Sportmonks Pinnacle / 国际盘（±4h 窗口同对阵）逐结果最大离散 < 5pp
     模  DC v1.1（W1 同参移植，xG 衰减拟合）收缩后最优方向 ≥ 53% 可推线
  4) 三关全过 → promoted；任一 fail → killed；否则 screening（诚实）
  5) 证据链逐条标注（源 + 时间），写 model_runs 审计，修订史追加
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (ModelRun, SPMatch, SPSnapshot, SportmonksMatchData,
                      Verdict, VerdictRevision, utcnow)
from .align import Aligner
from .dc_model import DCModel, add_alias, fit as dc_fit, load_xg, predict as dc_predict, predict_line
from .gates import (breakeven_prob, dynamic_threshold, implied_probs,
                    market_gate, model_gate, price_gate, shrink_to_market)
from .intl_odds import sources_for_match
from .results_sync import has_results_proxy
from .sealchain import link_revision

# 向后兼容（tests / 外部调用）
# implied_probs / breakeven_prob 由 gates 提供

_MODEL_CACHE: dict[str, DCModel] = {}


def canonical_payload(payload: dict) -> str:
    """规范化 JSON：utf-8 / sort_keys / 紧凑分隔符 —— 任何语言复算结果一致。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def seal_payload(payload: dict) -> tuple[str, str]:
    cj = canonical_payload(payload)
    return cj, hashlib.sha256(cj.encode("utf-8")).hexdigest()


POOL_LABEL = {"had": "胜平负", "hhad": "让球胜平负"}


def _model_cache_key(as_of: datetime) -> str:
    """日期 + 数据文件最新 mtime —— 当日新 dump 落档后缓存自动失效。"""
    st = get_settings()
    import glob
    import os
    mt = 0.0
    paths = [st.xg_data_path]
    if st.xg_extra_dir and os.path.isdir(st.xg_extra_dir):
        paths += glob.glob(os.path.join(st.xg_extra_dir, "*.csv"))
    for p in paths:
        try:
            if p and os.path.exists(p):
                mt = max(mt, os.path.getmtime(p))
        except OSError:
            pass
    return f"{as_of.strftime('%Y-%m-%d')}:{int(mt)}"


def _get_model(db: Session, aligner: Aligner, as_of: datetime) -> DCModel | None:
    """按（日期+数据新鲜度）缓存拟合；路径未配置/数据缺失 → None（模闸诚实 pending）。"""
    st = get_settings()
    key = _model_cache_key(as_of)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    if not st.xg_data_path:
        return None
    try:
        df = load_xg(st.xg_data_path, st.xg_extra_dir)
        model = dc_fit(df, as_of=as_of, halflife_days=st.dc_halflife_days,
                       window_days=st.dc_window_days, rho=st.dc_rho,
                       min_matches=st.dc_min_matches)
        # 为规范中文队名建键：understat 英文名 → aligner → canonical
        for raw in list(model.attack.keys()):
            add_alias(model, raw, aligner.resolve(raw))
        model.source = "goals_proxy" if has_results_proxy(st.xg_extra_dir) else "xg"
        _MODEL_CACHE[key] = model
        return model
    except Exception:
        return None


def _evidence(match: SPMatch, snap: SPSnapshot, pool: str, intl_rows: list,
              model: DCModel | None, pred, now_cn: str) -> list[dict]:
    ev = [{
        "tag": "已核验", "t": f"竞彩官方 SP（{POOL_LABEL[pool]}）",
        "d": f"{snap.sp_h:.2f} / {snap.sp_d:.2f} / {snap.sp_a:.2f}"
             + (f"（让球线 {snap.goal_line}）" if snap.goal_line else ""),
        "src": f"sporttery 采集器 · cutoff {snap.captured_at}",
    }]
    for r in intl_rows:
        ev.append({
            "tag": "已核验", "t": f"国际盘 · {r.source}",
            "d": f"{r.sp_h:.2f} / {r.sp_d:.2f} / {r.sp_a:.2f}",
            "src": f"the-odds-api · 拉取 {r.retrieved_at}",
        })
    if model is not None and pred is not None:
        ev.append({
            "tag": "已核验", "t": "DC v1.1 预测（市场收缩后）",
            "d": f"{pred.p_home:.1%} / {pred.p_draw:.1%} / {pred.p_away:.1%}"
                 f"（λ 主 {pred.lambda_home:.2f} · 客 {pred.lambda_away:.2f}）",
            "src": (f"{'football-data 进球代理' if model.source == 'goals_proxy' else 'Understat xG'}"
                    f" · 衰减窗口 {model.window_days}d · 拟合至 {model.as_of:%Y-%m-%d}"),
        })
    else:
        ev.append({
            "tag": "仅背景", "t": "DC 模型",
            "d": "该对阵不在 xG 强度表内（非五大联赛或窗口数据不足）",
            "src": "Understat · 2019-2025",
        })
    ev.append({
        "tag": "仅背景", "t": "首发确认",
        "d": "W4 接入 API-Football 后纳入模闸",
        "src": "—",
    })
    return ev


def build_verdicts(db: Session, trade_date: str, now_cn: str,
                   window_start: str | None = None, window_end: str | None = None) -> list[Verdict]:
    st = get_settings()
    q = select(SPMatch)
    if window_start and window_end:
        q = q.where(SPMatch.kickoff >= window_start, SPMatch.kickoff <= window_end)
    else:
        q = q.where(SPMatch.kickoff >= now_cn)
    matches = db.scalars(q).all()
    if not matches:
        return []

    aligner = Aligner(db)
    as_of = datetime.strptime(now_cn[:19], "%Y-%m-%d %H:%M:%S")
    model = _get_model(db, aligner, as_of)

    # 冻结纪律（W6 深审查）：promoted/settled 判决永不重建 ——
    # 封存后的结论不可被后续数据改写（修订史只属于 screening/killed 的演化）。
    existing = {v.id: v for v in db.scalars(
        select(Verdict).where(Verdict.match_id.in_([m.match_id for m in matches])))}
    frozen_ids = {v.match_id for v in existing.values()
                  if v.status == "promoted" or v.settled is not None}
    matches = [m for m in matches if m.match_id not in frozen_ids]
    if not matches:
        return []

    # 每场最新 had / hhad 快照（SQL 聚合，不拉全史）
    ids = [m.match_id for m in matches]
    sub = (
        select(SPSnapshot.match_id, SPSnapshot.pool, func.max(SPSnapshot.captured_at).label("mx"))
        .where(SPSnapshot.match_id.in_(ids))
        .group_by(SPSnapshot.match_id, SPSnapshot.pool)
        .subquery()
    )
    latest: dict[tuple[str, str], SPSnapshot] = {}
    for s in db.execute(
        select(SPSnapshot).join(
            sub,
            and_(SPSnapshot.match_id == sub.c.match_id,
                 SPSnapshot.pool == sub.c.pool,
                 SPSnapshot.captured_at == sub.c.mx),
        )
    ).scalars():
        latest[(s.match_id, s.pool)] = s

    # ---- 第一阶段：原始材料 ----
    stage: list[dict] = []
    for m in matches:
        pool = "had" if m.single_flag else "hhad"
        snap = latest.get((m.match_id, pool))
        if snap is None:
            pool = "hhad" if pool == "had" else "had"
            snap = latest.get((m.match_id, pool))
        if snap is None:
            continue
        if pool == "hhad" and not (snap.goal_line or "").strip():
            # 让球盘没有让球线时不能退化成 1x2 结算，否则标签与口径不一致。
            continue
        try:
            p_h, p_d, p_a, rake = implied_probs(snap.sp_h, snap.sp_d, snap.sp_a)
        except ValueError:
            # 单条历史脏快照（SP=1.0 等）不能拖垮整日判决；新数据由契约拦截。
            continue
        stage.append({"m": m, "snap": snap, "pool": pool,
                      "had_snap": latest.get((m.match_id, "had")),
                      "probs": (p_h, p_d, p_a), "rake": rake})

    # ---- 第二阶段：动态价阈值 ----
    threshold = dynamic_threshold([s["rake"] for s in stage],
                                  pad=st.rake_pad, lo=st.rake_clamp_lo, hi=st.rake_clamp_hi)

    out: list[Verdict] = []
    for s in stage:
        m, snap, pool = s["m"], s["snap"], s["pool"]
        p_jc = s["probs"]
        rake = s["rake"]

        # 价闸
        pg = price_gate(rake, threshold)

        # 市闸：竞彩官方 had ⊕ 国际盘 h2h（必须同口径）。
        # 让球 hhad 的胜平负概率不能直接与 Pinnacle h2h 比，否则会把让球线差异
        # 误判成 20pp+ 的“市场分歧”，把所有非单关场次错误 kill。
        intl_rows = []
        intl_err = None
        market_snap = s.get("had_snap") or (snap if pool == "had" else None)
        if market_snap is not None:
            try:
                mp_h, mp_d, mp_a, _ = implied_probs(
                    market_snap.sp_h, market_snap.sp_d, market_snap.sp_a)
                sources: dict[str, tuple[float, float, float]] = {
                    "竞彩官方(去水)": (mp_h, mp_d, mp_a)}
            except ValueError:
                sources = {"竞彩官方(去水)": p_jc}
        else:
            sources = {"竞彩官方(去水)": p_jc}
        try:
            intl_rows = sources_for_match(db, m)
            for r in intl_rows:  # retrieved 倒序：同源多条时新快照优先（first-wins）
                key = f"{r.source}({r.home_raw})"
                if key not in sources:
                    sources[key] = implied_probs(r.sp_h, r.sp_d, r.sp_a)[:3]
            # Sportmonks Pinnacle 1X2 已是去水概率，可与竞彩官方直接做同口径对照；
            # 有它时不再依赖 The Odds API 才能过市闸。
            sm = db.get(SportmonksMatchData, m.match_id)
            if sm is not None and isinstance(sm.odds, dict):
                try:
                    triple = (float(sm.odds["home"]), float(sm.odds["draw"]),
                              float(sm.odds["away"]))
                    if abs(sum(triple) - 1.0) < 0.05 and min(triple) > 0:
                        key = f"Sportmonks({sm.bookmaker or 'market'})"
                        sources.setdefault(key, triple)
                except (KeyError, TypeError, ValueError):
                    pass
        except Exception as e:
            intl_err = f"{type(e).__name__}: {e}"[:120]
        mg = market_gate(sources, st.market_div_threshold)
        mg.detail["verdict_pool"] = pool
        mg.detail["market_pool"] = "had" if market_snap is not None else pool
        if pool == "hhad" and market_snap is not None:
            mg.detail["note"] = "hhad 判决使用 had 做同口径市场一致性；让球盘精确 spreads 待接入"
        if market_snap is None and pool == "hhad":
            mg.detail["reason"] = "hhad 缺少 had 快照，无法同口径对照国际盘"
        if intl_err:
            mg.detail["intl_error"] = intl_err

        # 模闸：DC 预测（hhad 按让球线调整口径）→ 收缩 → 可推线
        pred = None
        if model is not None:
            line_val = None
            if pool == "hhad" and snap.goal_line:
                try:
                    line_val = float(snap.goal_line)
                except ValueError:
                    line_val = None
            if line_val is not None:
                pred = predict_line(model, m.home, m.away, line_val)
            else:
                pred = dc_predict(model, m.home, m.away)
        p_model = None
        if pred is not None:
            p_model = shrink_to_market((pred.p_home, pred.p_draw, pred.p_away), p_jc)
        dg = model_gate(p_model, (snap.sp_h, snap.sp_d, snap.sp_a), st.model_conf_threshold)
        if model is not None:
            dg.detail["engine_source"] = model.source

        gates = {"price": pg.as_dict(), "market": mg.as_dict(), "model": dg.as_dict()}
        pick = dg.detail.get("pick")

        # 审计日志（死因与闸门日志 100% 一致的基础）
        for g in (pg, mg, dg):
            db.add(ModelRun(match_id=m.match_id, run_date=trade_date, gate=g.gate,
                            result=g.result, detail=g.detail))

        all_pass = all(g["result"] == "pass" for g in gates.values())
        any_fail = any(g["result"] == "fail" for g in gates.values())
        status = "promoted" if all_pass else ("killed" if any_fail else "screening")

        evidence = _evidence(m, snap, pool, intl_rows, model, pred, now_cn)

        payload = {
            "id": f"v{trade_date}-{m.match_no}",
            "trade_date": trade_date,
            "match_id": m.match_id, "match_no": m.match_no,
            "league": m.league, "home": m.home, "away": m.away,
            "kickoff": m.kickoff, "pool": pool, "goal_line": snap.goal_line or "",
            "sp": {"h": snap.sp_h, "d": snap.sp_d, "a": snap.sp_a},
            "probs": {"home": round(p_jc[0], 4), "draw": round(p_jc[1], 4), "away": round(p_jc[2], 4)},
            "rake": round(rake, 4),
            "rake_threshold": round(threshold, 4),
            "breakeven": {"home": round(breakeven_prob(snap.sp_h), 4),
                          "draw": round(breakeven_prob(snap.sp_d), 4),
                          "away": round(breakeven_prob(snap.sp_a), 4)},
            "gates": gates,
            "model": {"shrunk": [round(x, 4) for x in p_model] if p_model else None,
                      "raw": [round(pred.p_home, 4), round(pred.p_draw, 4),
                              round(pred.p_away, 4)] if pred else None,
                      "pick": pick,
                      "engine": f"Dixon-Coles v1.1 (rho={st.dc_rho}, halflife={st.dc_halflife_days}d)"},
            "evidence": evidence,
            "status": status,
            "data_cutoff": snap.captured_at,
            "generated_at": now_cn,
            "engine": "jieqiu-w3.0",
        }
        cj, digest = seal_payload(payload)

        has_rev = db.scalar(
            select(VerdictRevision.id).where(
                VerdictRevision.verdict_id == payload["id"],
                VerdictRevision.payload_hash == digest))
        new_rev = None
        if has_rev is None:
            new_rev = VerdictRevision(verdict_id=payload["id"], payload=payload,
                                      payload_hash=digest, data_cutoff=snap.captured_at,
                                      trade_date=trade_date)
            db.add(new_rev)
            db.flush()  # 拿到 created_at/id 再接链
            link_revision(db, new_rev)

        v = db.get(Verdict, payload["id"])
        if v is None:
            v = Verdict(id=payload["id"])
            db.add(v)
        v.trade_date = trade_date
        v.match_id = m.match_id
        v.match_no = m.match_no
        v.league = m.league
        v.home = m.home
        v.away = m.away
        v.kickoff = m.kickoff
        v.pool = pool
        v.goal_line = snap.goal_line or ""
        v.sp_h, v.sp_d, v.sp_a = snap.sp_h, snap.sp_d, snap.sp_a
        v.rake = round(rake, 4)
        v.p_home, v.p_draw, v.p_away = round(p_jc[0], 4), round(p_jc[1], 4), round(p_jc[2], 4)
        v.model_h = round(p_model[0], 4) if p_model else None
        v.model_d = round(p_model[1], 4) if p_model else None
        v.model_a = round(p_model[2], 4) if p_model else None
        v.pick = pick
        v.rake_threshold = round(threshold, 4)
        v.status = status
        v.gates = gates
        v.payload = payload
        v.payload_hash = digest
        # 已封存判决产生新修订后，当前 payload 的封存时间随最新修订前移；
        # 否则详情页会出现“数据截止晚于封存时间”的矛盾。
        if new_rev is not None and v.sealed_at is not None:
            v.sealed_at = new_rev.created_at
        out.append(v)
    db.commit()
    return out


def promote_seal(db: Session, trade_date: str) -> int:
    """对当日 screening 判决统一盖章 sealed_at（终审通过后调用）。"""
    rows = db.scalars(select(Verdict).where(Verdict.trade_date == trade_date)).all()
    n = 0
    for v in rows:
        if v.sealed_at is None:
            v.sealed_at = utcnow()
            n += 1
    db.commit()
    return n
