"""人设语气翻译 CLI。

    python -m app.persona_cli models
    python -m app.persona_cli test --persona laopao --text "今天主看曼城..."
    python -m app.persona_cli warm --date 2026-11-05
"""
from __future__ import annotations

import argparse
import json

from .db import SessionLocal
from .modules import persona_llm


def main() -> None:
    parser = argparse.ArgumentParser(description="persona copy LLM")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models")
    p_test = sub.add_parser("test")
    p_test.add_argument("--persona", default="zhuanjia",
                        choices=tuple(persona_llm.PERSONAS))
    p_test.add_argument("--text", required=True)
    p_warm = sub.add_parser("warm")
    p_warm.add_argument("--date", required=True)
    p_warm.add_argument("--persona", action="append",
                        choices=tuple(persona_llm.PERSONAS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "models":
            persona_llm.ensure_default_models(db)
            out = [{"name": r.name, "base_url": r.base_url, "model": r.model,
                    "priority": r.priority, "enabled": r.enabled,
                    "key": persona_llm.mask_key(r.api_key_enc),
                    "fail_count": r.fail_count, "last_error": r.last_error}
                   for r in persona_llm.list_models(db)]
        elif args.cmd == "test":
            res = persona_llm.translate(db, args.text, args.persona, use_cache=False)
            out = {"model": res.model, "persona": res.persona,
                   "latency_ms": res.latency_ms, "text": res.text}
        else:
            personas = tuple(args.persona or persona_llm.PERSONAS)
            out = persona_llm.warm_verdicts(db, args.date, personas)
    except persona_llm.PersonaLLMError as exc:
        out = {"ok": False, "error": str(exc)}
    finally:
        db.close()
    print(json.dumps(out, ensure_ascii=False, sort_keys=True)
          if args.json else out)


if __name__ == "__main__":
    main()
