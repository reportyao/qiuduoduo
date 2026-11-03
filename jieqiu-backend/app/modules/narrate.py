"""叙述生成（W4 流式管道）。

- 结构层（数字）永远来自 verdict payload，模板只负责包装 —— 数字不进 LLM
- provider 抽象：LLM 未配置/失败 → 模板兜底（gate：弱网降级模板不出错）
- SSE 输出：{"delta": "..."} 分片 + {"done": true, "template_id": ...}
"""
from __future__ import annotations

from ..models import Verdict

TEMPLATES = {
    "zhuanjia": {
        "promoted": ("{home} vs {away}。{pick}，模型置信 {top}%。"
                     "抽水 {rake}%（阈值 {thr}%），市场离散 {div}。"
                     "成本已算清，判断已封存。剩下的交给比赛。"),
        "screening": ("{home} vs {away}：复核中。价闸已过（抽水 {rake}%）。"
                      "{wait}—— 过了我会说，没过我不推。"),
        "killed": ("{home} vs {away}，不推。死因：{why}。"
                   "看不懂的不碰，这是纪律。"),
    },
    "laopao": {
        "promoted": ("兄弟，{home}打{away}，这场能上：{pick}，人家模型有 {top}% 的底。"
                     "抽水才 {rake}%，市场也没吵起来。账我给你算明白了，上不上你定。"),
        "screening": ("兄弟，{home}对{away}还在复核。价钱还行（{rake}%），{wait}。"
                      "别急，好饭不怕晚。"),
        "killed": ("兄弟，{home}这场咱撤：{why}。省下的都是赚的，输钱不输阵。"),
    },
    "meng": {
        "promoted": ("主人～{home} vs {away}，人家检查完啦！{pick}，置信 {top}% 哦～"
                     "抽水只有 {rake}%，三关都过了呢！详情人家都封好啦 ♡"),
        "screening": ("主人～{home}对{away}人家还在复核中…{wait}。"
                      "复核完人家第一时间飞奔来报 ♡"),
        "killed": ("呜…{home}这场人家不能让主人上：{why}。不放行的时候，人家最认真！(っ•̀ω•́)っ"),
    },
}

_WAIT_TEXT = {
    "market": "在等国际盘口径收敛",
    "model": "在等 xG 强度覆盖 / 首发确认",
    "price": "在等价格回落到阈值内",
}


def _fmt_pct(x: float | None, default: str = "—") -> str:
    return f"{x*100:.1f}" if x is not None else default


def build_narration(v: Verdict, persona: str = "zhuanjia") -> tuple[str, str]:
    """(text, template_id)。结构数字全部取自 payload/列，模板不出错兜底在 stream 层。"""
    p = (v.payload or {})
    gates = v.gates or {}
    shrunk = (p.get("model") or {}).get("shrunk") or [0.0, 0.0, 0.0]
    ctx = {
        "home": v.home, "away": v.away,
        "rake": _fmt_pct(v.rake),
        "thr": _fmt_pct(v.rake_threshold),
        "top": _fmt_pct(max(shrunk)),
        "pick": (v.pick or {}).get("dir", "无 pick（复核中）"),
        "div": _fmt_pct((gates.get("market", {}).get("detail") or {}).get("divergence")),
    }
    # 等待原因：首个 pending 闸
    wait = "在等数据源覆盖"
    for g in ("market", "model", "price"):
        if gates.get(g, {}).get("result") == "pending_data":
            wait = _WAIT_TEXT.get(g, wait)
            break
    ctx["wait"] = wait
    # 死因
    why = "过闸失败"
    for g in ("price", "market", "model"):
        if gates.get(g, {}).get("result") == "fail":
            if g == "price":
                why = f"抽水 {ctx['rake']}% 超阈值"
            elif g == "market":
                why = f"多源离散 {ctx['div']}pp"
            else:
                why = "模型置信不足"
            break
    ctx["why"] = why

    status = v.status if v.status in ("promoted", "screening", "killed") else "screening"
    tpl_set = TEMPLATES.get(persona, TEMPLATES["zhuanjia"])
    tpl = tpl_set.get(status) or tpl_set["screening"]
    return tpl.format(**ctx), f"{persona}.{status}"


def stream_chunks(text: str, chunk: int = 10):
    """把文本切成分片（模拟流式；LLM 接入后由 provider 直接产 chunk）。"""
    for i in range(0, len(text), chunk):
        yield text[i:i + chunk]


def llm_available() -> bool:
    """LLM 接入计划在 v1.5；当前恒走模板（结构数字不进 LLM，降级即默认态）。"""
    return False


def generate_stream(v: Verdict, persona: str = "zhuanjia"):
    """产出 (kind, data) 序列：("delta", text)... ("done", meta)。任何异常走模板兜底。"""
    try:
        if llm_available():
            raise NotImplementedError  # v1.5 接入；当前必然走模板
        text, tid = build_narration(v, persona)
    except Exception:
        try:
            text, tid = build_narration(v, "zhuanjia")  # 兜底人设再兜底
        except Exception:
            text, tid = f"{v.home} vs {v.away}：数据整理中。", "fallback.minimal"
    for chunk in stream_chunks(text):
        yield "delta", chunk
    yield "done", {"template_id": tid, "persona": persona}
