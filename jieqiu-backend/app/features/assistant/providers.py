"""推送渠道适配器：MVP 只实现 JPush（Android），未配置时 dry-run。

扩展点：以后 APNs/FCM/微信 各加一个 PushProvider，不改 worker。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Protocol

import urllib.error
import urllib.request

logger = logging.getLogger("jieqiu.push")


@dataclass
class PushMessage:
    title: str
    body: str
    deeplink: str = ""
    extras: dict | None = None


@dataclass
class PushResult:
    ok: bool
    provider_msg_id: str = ""
    error: str = ""


class PushProvider(Protocol):
    name: str

    def send(self, tokens: list[str], msg: PushMessage) -> PushResult:
        ...


class JPushProvider:
    name = "jpush"

    def __init__(self) -> None:
        self.appkey = os.environ.get("JQ_JPUSH_APPKEY", "").strip()
        self.secret = os.environ.get("JQ_JPUSH_MASTER_SECRET", "").strip()
        self.dryrun = (os.environ.get("JQ_JPUSH_DRYRUN", "").strip() in ("1", "true", "yes")
                       or not self.appkey or not self.secret)

    def send(self, tokens: list[str], msg: PushMessage) -> PushResult:
        tokens = [t for t in tokens if t]
        if not tokens:
            return PushResult(False, error="no_token")
        if self.dryrun:
            mid = "dryrun:" + uuid.uuid4().hex[:16]
            logger.info("jpush dryrun tokens=%s title=%s deeplink=%s",
                        len(tokens), msg.title, msg.deeplink)
            return PushResult(True, provider_msg_id=mid)
        payload = {
            "platform": ["android"],
            "audience": {"registration_id": tokens},
            "notification": {
                "alert": msg.body,
                "android": {
                    "title": msg.title,
                    "extras": {"deeplink": msg.deeplink, **(msg.extras or {})},
                },
            },
            "options": {"time_to_live": 3600, "apns_production": False},
        }
        req = urllib.request.Request(
            "https://api.jpush.cn/v3/push",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Basic " + base64.b64encode(
                    f"{self.appkey}:{self.secret}".encode()).decode(),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8", "replace")
                data = json.loads(body or "{}")
                # JPush 对“audience 里没有有效 registration id”等业务错误
                # 仍可能返回 HTTP 200 + error 字段，不能当成功。
                err = data.get("error")
                if isinstance(err, dict) and err:
                    return PushResult(
                        False,
                        error=f"jpush_{err.get('code', '')}:{err.get('message', '')}"[:300],
                    )
                return PushResult(True, provider_msg_id=str(data.get("msg_id", "")))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            return PushResult(False, error=f"http_{e.code}:{detail}")
        except Exception as e:  # noqa: BLE001 网络错误统一降级
            return PushResult(False, error=str(e)[:300])


PROVIDERS: dict[str, type] = {"jpush": JPushProvider}


def get_push_provider(name: str = "jpush") -> PushProvider:
    return PROVIDERS.get(name, JPushProvider)()
