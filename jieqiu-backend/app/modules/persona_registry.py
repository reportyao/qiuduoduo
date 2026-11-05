"""人设 profile 与文案槽位：后台可配置的底座。

- profile 只存“怎么说”，不存方向/概率/条件。
- slot 是后台可编辑的兜底模板，当前供后台/API 读取；运行时回退仍在 narrate.py，前端尚未消费。
- 任何字段变更只 bump version，不改历史推荐文案。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PersonaCopySlot, PersonaProfile

DEFAULT_PROFILES = {
    "zhuanjia": {
        "name": "理性专家", "address": "你", "tone": "冷静 · 简单直接",
        "style_prompt": "冷静、克制、结论先行；短句；不用 emoji；不煽动；方向必须说清楚。",
        "max_chars": 220, "emoji_policy": "none", "allowed_emoji": "",
    },
    "laopao": {
        "name": "感性老炮", "address": "兄弟", "tone": "兄弟 · 幽默 · 有情绪",
        "style_prompt": "口语、接地气、有情绪但不煽动；可以损友式提醒；不打包票；方向必须说清楚。",
        "max_chars": 260, "emoji_policy": "none", "allowed_emoji": "",
    },
    "meng": {
        "name": "元气搭子", "address": "你", "tone": "活泼 · 直白 · 不绕弯",
        "style_prompt": "亲近、活泼、短句、少量语气词；不暧昧、不卖萌到幼稚；方向必须说清楚。",
        "max_chars": 240, "emoji_policy": "limited", "allowed_emoji": "～",
    },
}

DEFAULT_SLOTS = {
    "today_pick": "{address}，今天主看 {home} vs {away}。倾向：{direction}。把握度：{confidence}。因为：{reason}。除非：{invalidator}。",
    "plan_intro": "{address}，今天参考组合是 {legs} 串 1。",
    "plan_why_not": "不建议加到更多腿：{cost_delta}，{correlation_note}。",
    "locked": "还有 {remaining} 条已复核观点。",
    "paywall": "解锁今日全部判断与组合。",
    "empty": "今天没有足够值得主看的场次。",
    "postmatch": "昨天主看 {result}，过程 {process}。",
    "review_badge": "AI 复核 · {time} · v{version}",
    "push": "今日判断已更新：{count} 条观点。",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_seeded(db: Session) -> None:
    changed = False
    rows = {p.id: p for p in db.scalars(select(PersonaProfile)).all()}
    for pid, p in DEFAULT_PROFILES.items():
        row = rows.get(pid)
        if row is None:
            db.add(PersonaProfile(id=pid, **p, version=1, enabled=True))
            changed = True
        elif pid == "meng" and row.name == "萌妹萝莉":
            # 旧默认人设带未成年化/主仆暗示，不适合博彩类应用；
            # 只迁移仍是旧默认值的行，运营改过的配置不覆盖。
            for field in ("name", "address", "tone", "style_prompt", "allowed_emoji"):
                setattr(row, field, p[field])
            row.version += 1
            changed = True
    if changed:
        db.commit()

    existing_slots = {(s.persona_id, s.slot_key)
                      for s in db.scalars(select(PersonaCopySlot)).all()}
    changed = False
    for pid in DEFAULT_PROFILES:
        for key, template in DEFAULT_SLOTS.items():
            if (pid, key) not in existing_slots:
                db.add(PersonaCopySlot(persona_id=pid, slot_key=key,
                                       template=template, version=1, enabled=True))
                changed = True
    if changed:
        db.commit()

def list_profiles(db: Session) -> list[PersonaProfile]:
    ensure_seeded(db)
    return list(db.scalars(select(PersonaProfile)
                           .order_by(PersonaProfile.id)).all())


def get_profile(db: Session, persona_id: str) -> PersonaProfile | None:
    ensure_seeded(db)
    return db.get(PersonaProfile, persona_id)


def list_slots(db: Session, persona_id: str | None = None) -> list[PersonaCopySlot]:
    ensure_seeded(db)
    q = select(PersonaCopySlot)
    if persona_id:
        q = q.where(PersonaCopySlot.persona_id == persona_id)
    return list(db.scalars(q.order_by(PersonaCopySlot.persona_id,
                                      PersonaCopySlot.slot_key)).all())


def public_payload(db: Session) -> dict:
    ensure_seeded(db)
    profiles = list_profiles(db)
    slots = list_slots(db)
    version = max([p.version for p in profiles] + [s.version for s in slots] + [1])
    return {
        "version": version,
        "profiles": [
            {"id": p.id, "name": p.name, "address": p.address, "tone": p.tone,
             "max_chars": p.max_chars, "emoji_policy": p.emoji_policy,
             "allowed_emoji": p.allowed_emoji}
            for p in profiles if p.enabled
        ],
        "slots": [
            {"persona_id": s.persona_id, "slot_key": s.slot_key,
             "template": s.template}
            for s in slots if s.enabled
        ],
    }


def update_profile(db: Session, persona_id: str, *, address: str | None = None,
                   tone: str | None = None, style_prompt: str | None = None,
                   max_chars: int | None = None, emoji_policy: str | None = None,
                   allowed_emoji: str | None = None) -> PersonaProfile:
    row = get_profile(db, persona_id)
    if row is None:
        raise ValueError("persona not found")
    if address is not None:
        row.address = address.strip()[:16]
    if tone is not None:
        row.tone = tone.strip()[:64]
    if style_prompt is not None:
        row.style_prompt = style_prompt.strip()[:1200]
    if max_chars is not None:
        row.max_chars = max(60, min(600, int(max_chars)))
    if emoji_policy is not None:
        row.emoji_policy = emoji_policy if emoji_policy in ("none", "limited", "free") else "none"
    if allowed_emoji is not None:
        row.allowed_emoji = allowed_emoji.strip()[:32]
    row.version += 1
    db.commit()
    db.refresh(row)
    return row


def update_slot(db: Session, persona_id: str, slot_key: str, template: str) -> PersonaCopySlot:
    ensure_seeded(db)
    if get_profile(db, persona_id) is None:
        raise ValueError("persona not found")
    if slot_key not in DEFAULT_SLOTS:
        raise ValueError("slot not found")
    row = db.scalar(select(PersonaCopySlot).where(
        PersonaCopySlot.persona_id == persona_id,
        PersonaCopySlot.slot_key == slot_key))
    if row is None:
        row = PersonaCopySlot(persona_id=persona_id, slot_key=slot_key,
                              template=template, version=1)
        db.add(row)
    else:
        row.template = template.strip()[:2000]
        row.version += 1
    db.commit()
    db.refresh(row)
    return row
