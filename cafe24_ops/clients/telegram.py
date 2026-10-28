"""텔레그램 봇 알림 — 매일 브리핑 + 대시보드 링크를 PC/모바일 텔레그램으로.

필요: TELEGRAM_BOT_TOKEN (@BotFather 로 봇 생성), TELEGRAM_CHAT_ID (봇에게 아무 메시지 보낸 뒤
       https://api.telegram.org/bot<토큰>/getUpdates 의 chat.id — 그룹이면 음수)
선택: DASHBOARD_URL (메시지 하단 버튼 링크)
"""
from __future__ import annotations

import requests

from .. import config

REQUIRED_ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def send(text: str, url: str | None = None, url_label: str = "대시보드 열기") -> bool:
    token, chat = config.env("TELEGRAM_BOT_TOKEN"), config.env("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    payload: dict = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    link = url or config.env("DASHBOARD_URL")
    if link:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": url_label, "url": link}]]}
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=15)
    return r.status_code == 200 and r.json().get("ok", False)


def send_document(data: bytes, filename: str, caption: str = "") -> bool:
    """주간 리포트 .docx 등 파일 전송."""
    token, chat = config.env("TELEGRAM_BOT_TOKEN"), config.env("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={"chat_id": chat, "caption": caption[:1000]},
                      files={"document": (filename, data)}, timeout=60)
    return r.status_code == 200 and r.json().get("ok", False)
