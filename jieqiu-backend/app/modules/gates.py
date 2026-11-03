"""三道闸纯数学模块（可独立测试）：价 / 市 / 模。

设计对齐 PRD §三关 与 UI 原型：
- 价闸：抽水 ≤ 当日动态阈值（当日候选场中位数 + pad，夹 [10%, 13%]）
- 市闸：≥2 个去水口径，逐结果最大离散度 < 5pp；单源 → pending_data（诚实）
- 模闸：DC v1.1 收缩后最优方向 ≥ 53% 可推线；无模型预测 → pending_data
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median


# ---------- 通用概率数学 ----------

def implied_probs(sp_h: float, sp_d: float, sp_a: float) -> tuple[float, float, float, float]:
    """赔率 → (p_h, p_d, p_a, rake)。去水为比例法：p_i = (1/sp_i)/Σ(1/sp)。"""
    for sp in (sp_h, sp_d, sp_a):
        if sp <= 1.0:
            raise ValueError(f"SP must be > 1.0, got {sp}")
    imp = [1.0 / sp for sp in (sp_h, sp_d, sp_a)]
    s = sum(imp)
    if s <= 0:
        raise ValueError("implied sum must be positive")
    rake = 1.0 - 1.0 / s
    return imp[0] / s, imp[1] / s, imp[2] / s, rake


def breakeven_prob(sp: float) -> float:
    """押注该赔率打平所需的胜率 = 1 / sp。"""
    if sp <= 1.0:
        raise ValueError(f"SP must be > 1.0, got {sp}")
    return 1.0 / sp


# ---------- 价闸 ----------

def dynamic_threshold(rakes: list[float], pad: float, lo: float, hi: float) -> float:
    """当日动态阈值：中位数 + pad，夹在 [lo, hi]。候选不足时用 lo（保守）。"""
    usable = [r for r in rakes if r > 0]
    if len(usable) < 5:
        return lo
    return min(hi, max(lo, median(usable) + pad))


@dataclass
class GateResult:
    gate: str
    result: str          # pass / fail / pending_data
    detail: dict

    def as_dict(self) -> dict:
        return asdict(self)


def price_gate(rake: float, threshold: float) -> GateResult:
    return GateResult(
        gate="price",
        result="pass" if rake <= threshold else "fail",
        detail={
            "rake": round(rake, 4),
            "threshold": round(threshold, 4),
            "rule": "抽水 ≤ 当日动态阈值（当日候选场中位数 + 3pp，夹 [10%, 13%]）",
        },
    )


# ---------- 市闸 ----------

def divergence(sources: dict[str, tuple[float, float, float]]) -> float:
    """逐结果最大离散度：max over (H/D/A) of (max_i p_i − min_i p_i)。输入均为去水后概率。"""
    if len(sources) < 2:
        raise ValueError("divergence needs >= 2 sources")
    spread = 0.0
    for idx in range(3):
        vals = [p[idx] for p in sources.values()]
        spread = max(spread, max(vals) - min(vals))
    return spread


def market_gate(sources: dict[str, tuple[float, float, float]],
                threshold: float) -> GateResult:
    if len(sources) < 2:
        return GateResult(
            gate="market", result="pending_data",
            detail={"sources": sorted(sources.keys()),
                    "reason": "国际盘源不足（未配置 the-odds-api key 或该场未覆盖）"},
        )
    div = divergence(sources)
    per_source = {k: [round(x, 4) for x in v] for k, v in sources.items()}
    return GateResult(
        gate="market",
        result="pass" if div < threshold else "fail",
        detail={"divergence": round(div, 4), "threshold": threshold,
                "sources": per_source,
                "rule": "≥2 源去水后逐结果最大离散度 < 5pp"},
    )


# ---------- 模闸 ----------

def shrink_to_market(p_model: tuple[float, float, float],
                     p_market: tuple[float, float, float],
                     shrink_at: float = 0.08, factor: float = 0.5
                     ) -> tuple[float, float, float]:
    """W1 v1.1 收缩纪律：与市场偏差 > 8pp 的结果，偏差砍半后归一。"""
    out = []
    for m, k in zip(p_model, p_market):
        out.append(m * factor + k * (1 - factor) if abs(m - k) > shrink_at else m)
    s = sum(out)
    if s <= 0:
        raise ValueError("shrunk probs sum <= 0")
    return out[0] / s, out[1] / s, out[2] / s


def best_pick(p_model: tuple[float, float, float],
              sp: tuple[float, float, float]) -> dict:
    """最优方向 = 收缩概率 × 官方 SP 的 EV 最大者。EV = p·sp − 1。"""
    dirs = ("主胜", "平局", "客胜")
    evs = [p * s - 1.0 for p, s in zip(p_model, sp)]
    i = max(range(3), key=lambda j: evs[j])
    return {"dir": dirs[i], "prob": round(p_model[i], 4),
            "sp": sp[i], "ev": round(evs[i], 4)}


def model_gate(p_model: tuple[float, float, float] | None,
               sp: tuple[float, float, float],
               conf_threshold: float) -> GateResult:
    if p_model is None:
        return GateResult(
            gate="model", result="pending_data",
            detail={"reason": "DC 模型无该对阵预测（队名未入 xG 库或窗口数据不足）"},
        )
    top = max(p_model)
    pick = best_pick(p_model, sp)
    # 放行必须针对“实际会发布的 pick”，不能只看三方向最高概率：
    # 否则 55% 的主胜可以让 20% 的客胜高赔 pick 过关，用户看到的置信与闸门不一致。
    pick_prob = pick["prob"]
    detail = {"shrunk": [round(x, 4) for x in p_model], "top": round(top, 4),
              "pick_prob": pick_prob, "threshold": conf_threshold, "pick": pick,
              "rule": "收缩后最优方向概率 ≥ 53% 可推线（首发确认检查 W4 接入 API-Football）"}
    return GateResult(
        gate="model",
        result="pass" if pick_prob >= conf_threshold else "fail",
        detail=detail,
    )
