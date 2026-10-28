"""Slack Incoming Webhook 알림 (선택). 없으면 토큰이 끊겨도 아무도 모른다 — keek 36일 결측 사례."""
from __future__ import annotations

import requests

from .. import config

REQUIRED_ENV = ("SLACK_WEBHOOK_URL",)


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def send(text: str) -> bool:
    url = config.env("SLACK_WEBHOOK_URL")
    if not url:
        return False
    r = requests.post(url, json={"text": text}, timeout=15)
    return r.status_code == 200
