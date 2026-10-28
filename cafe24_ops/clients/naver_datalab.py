"""네이버 데이터랩(검색어트렌드) — 경쟁사 브랜드 상대 트렌드 지수(0~100, 절대 검색량 아님).

필요: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET (developers.naver.com, 무료·즉시)
"""
from __future__ import annotations

from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")
URL = "https://openapi.naver.com/v1/datalab/search"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


class NaverDataLab:
    def __init__(self):
        self.headers = {"X-Naver-Client-Id": config.env("NAVER_CLIENT_ID"),
                        "X-Naver-Client-Secret": config.env("NAVER_CLIENT_SECRET"),
                        "Content-Type": "application/json"}

    def trend(self, keywords: list[str], start_date: str, end_date: str) -> list[dict[str, Any]]:
        """[{'title': 브랜드, 'data': [{'period': 'YYYY-MM-DD', 'ratio': 12.3}, ...]}]"""
        groups = [{"groupName": k, "keywords": [k]} for k in keywords[:5]]
        r = requests.post(URL, headers=self.headers, json={
            "startDate": start_date, "endDate": end_date, "timeUnit": "date", "keywordGroups": groups,
        }, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"DataLab {r.status_code}: {r.text[:300]}")
        return r.json().get("results", [])
