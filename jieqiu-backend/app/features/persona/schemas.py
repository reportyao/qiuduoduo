"""公开人设配置响应。"""
from __future__ import annotations

from pydantic import BaseModel


class PersonaPublic(BaseModel):
    id: str
    name: str
    address: str
    tone: str
    max_chars: int
    emoji_policy: str
    allowed_emoji: str


class CopySlotPublic(BaseModel):
    persona_id: str
    slot_key: str
    template: str


class PersonaConfigResponse(BaseModel):
    version: int
    profiles: list[PersonaPublic]
    slots: list[CopySlotPublic]
