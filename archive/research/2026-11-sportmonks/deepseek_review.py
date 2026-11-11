#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 DeepSeek（TokenRhythm 中转）独立评审 Sportmonks 重构方案。"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY = ""
for line in (ROOT / "jieqiu-backend" / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("JQ_PERSONA_LLM_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
        break
if not KEY:
    sys.exit("no key")

PLAN = (ROOT / "docs" / "sportmonks-refactor-plan.md").read_text(encoding="utf-8")
CONTEXT = (ROOT / "docs" / "sm_review_context.md").read_text(encoding="utf-8")

SYSTEM = (
    "你是一名独立的资深架构评审，与方案作者无任何关系，职责是挑毛病而不是认同。"
    "评审对象是一份'体育竞彩赛前预测产品接入 Sportmonks API 的重构方案'。"
    "请从四个维度严格审查：\n"
    "1) 错误：技术事实错误、对 API/定价/能力的误解、逻辑不自洽；\n"
    "2) 遗漏：没考虑到的风险、数据源、环节、边界条件、成本项；\n"
    "3) 优化：有明显更优做法的地方；\n"
    "4) 补充：值得增加但方案没提的价值点。\n"
    "要求：每条给【严重度 P0/P1/P2】+【位置】+【问题】+【具体建议】；"
    "不要复述方案；不要客套；总输出控制在 2500 字以内、最多 12 条，只保留最重要的发现；不确定的事标注'需验证'。"
    "用中文输出。")

USER = CONTEXT + "\n\n===== 待评审方案全文 =====\n" + PLAN

def call_once(extra: dict) -> tuple[str, str]:
    payload = {
        "model": "deepseek-v4.1-flash-1017",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "max_tokens": 8000,
        "temperature": 0.3,
        "stream": True,
    }
    payload.update(extra)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://tokenrhythm.studio/v1/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    parts: list[str] = []
    finish = None
    err = None
    try:
        with opener.open(req, timeout=900) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    err = str(chunk["error"])[:200]
                    break
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                if delta.get("content"):
                    parts.append(delta["content"])
                fr = (chunk.get("choices") or [{}])[0].get("finish_reason")
                if fr:
                    finish = fr
    except Exception as exc:  # noqa: BLE001
        err = str(exc)[:200]
    return "".join(parts).strip(), (err or finish or "")

out = ""
for extra in ({"reasoning_effort": "low"}, {"enable_thinking": False},
              {"thinking": {"type": "disabled"}}, {}):
    out, info = call_once(extra)
    print(f"variant={extra} -> chars={len(out)} info={info}", flush=True)
    if out:
        break
if not out:
    out = "[全部变体未取到 content]"
usage = {}
(ROOT / "docs" / "sm_deepseek_review.md").write_text(out, encoding="utf-8")
print(f"chars={len(out)} finish={finish}")
print(out)
