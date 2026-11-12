"""三种人设的对话文案渲染。

事实由调用方传入；这里只改语气，不改数字。
"""
from __future__ import annotations

PERSONAS = ("zhuanjia", "laopao", "meng")
NAMES = {"zhuanjia": "理性专家", "laopao": "感性老炮", "meng": "元气搭子"}


def _v(persona: str, key: str) -> str:
    return {
        "zhuanjia": {
            "daily_record": "昨天 {picks} 场，{hits} 中；最近 30 天，{hit_days} 天有命中。",
            "buy": "{home} vs {away}：{pick}。这场已经过复核，详情在卡片里。",
            "why_not": "{home} vs {away} 这场我没给预测，原因在卡片里。",
            "postmortem": "最近的复盘在卡片里，输赢都写清楚。",
            "memory": "记下了：{key} = {value}。",
            "rest": "好，今天先到这里。明晚的预测照常。",
            "fallback": "我主要看今日预测、未出原因、复盘和你的偏好。你可以直接问。",
            "no_data": "这场的数据还不够，我先不给结论。",
            "no_record": "还没有可复盘的战绩，等有已结算的推荐我再报。",
        },
        "laopao": {
            "daily_record": "兄弟，昨天 {picks} 场中了 {hits} 场；最近 30 天，{hit_days} 天有收获。",
            "buy": "兄弟，{home} 打 {away}，我选 {pick}。这场账算过了，详情你看卡片。",
            "why_not": "兄弟，{home} 对 {away} 这场我没给，原因都写在卡片里，不瞎给。",
            "postmortem": "兄弟，最近的账都摆在这儿，输赢不藏。",
            "memory": "记上了兄弟：{key} = {value}。",
            "rest": "行，今天就到这儿。歇一晚，明天再来。",
            "fallback": "兄弟，今日预测、为啥不出、复盘、你的偏好，直接问就行。",
            "no_data": "兄弟，这场数据不够，我不硬给。",
            "no_record": "兄弟，还没可复盘的战绩，等有结算我再报。",
        },
        "meng": {
            "daily_record": "昨天 {picks} 场中 {hits} 场～最近 30 天有 {hit_days} 天命中。",
            "buy": "{home} vs {away}，我选 {pick}。这场我检查过啦，详情在卡片里～",
            "why_not": "{home} 对 {away} 这场我先不给预测，原因写在卡片里啦。",
            "postmortem": "最近的复盘我都记着，输赢都在卡片里～",
            "memory": "记住啦：{key} = {value}。",
            "rest": "好呀，今天先休息。明晚我照常来。",
            "fallback": "今日预测、为什么不出、复盘、你的偏好，都可以问我～",
            "no_data": "这场数据还不够，我先不硬给结论。",
            "no_record": "还没有可复盘的战绩，等有已结算的推荐我再报～",
        },
    }.get(persona, {}).get(key, "{fallback}")


_SLOT = {
    "daily_record": "assistant_daily_record",
    "buy": "assistant_buy_tonight",
    "why_not": "assistant_why_not",
    "postmortem": "assistant_postmortem",
    "memory": "assistant_memory",
    "rest": "assistant_status",
    "fallback": "assistant_fallback",
    "no_data": "assistant_empty",
}


def render(persona: str, key: str, db=None, **facts) -> str:
    persona = persona if persona in PERSONAS else "zhuanjia"
    template = ""
    if db is not None:
        try:
            from . import persona_registry
            slot_key = _SLOT.get(key, key)
            row = next((r for r in persona_registry.list_slots(db, persona)
                        if r.slot_key == slot_key and r.enabled), None)
            if row is not None:
                template = row.template
        except Exception:
            template = ""
    template = template or _v(persona, key)
    try:
        return template.format(**facts)
    except (KeyError, ValueError):
        return template


def style_fallback(persona: str, text: str) -> str:
    """没有专门模板时，至少保持称呼/语气，不改事实。"""
    if persona == "laopao":
        return f"兄弟，{text}"
    if persona == "meng" and not text.endswith("～"):
        return f"{text}～"
    return text
