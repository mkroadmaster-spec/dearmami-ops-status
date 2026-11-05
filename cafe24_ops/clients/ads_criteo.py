"""Criteo Marketing API — 일자별 광고비·노출·클릭·전환·매출 (무료, 광고주 본인 계정).

필요: CRITEO_CLIENT_ID, CRITEO_CLIENT_SECRET  (developers.criteo.com → My Apps → 앱 생성 → 광고주 동의(consent))
선택: CRITEO_ADVERTISER_ID (비우면 접근 가능한 전체 광고주 합산)
인증: OAuth2 client_credentials → https://api.criteo.com/oauth2/token (액세스 토큰 15분)
리포트: POST /{version}/statistics/report (dimensions Day, metrics Displays/Clicks/AdvertiserCost/SalesAllPc30d/RevenueGeneratedAllPc30d)
실 키로 첫 1회 응답 필드 검증 권장. 버전은 CRITEO_API_VERSION 으로 변경 가능.
"""
from __future__ import annotations

import csv
import io
from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("CRITEO_CLIENT_ID", "CRITEO_CLIENT_SECRET")
HOST = "https://api.criteo.com"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


class CriteoClient:
    def __init__(self):
        self.version = config.env("CRITEO_API_VERSION", "2025-04")
        r = requests.post(f"{HOST}/oauth2/token", data={
            "grant_type": "client_credentials", "client_id": config.env("CRITEO_CLIENT_ID"),
            "client_secret": config.env("CRITEO_CLIENT_SECRET")}, timeout=30)
        if r.status_code >= 400:
            raise PermissionError(f"Criteo 토큰 발급 실패 {r.status_code}: {r.text[:200]}")
        self.token = r.json()["access_token"]
        self.advertiser_id = config.env("CRITEO_ADVERTISER_ID")

    def daily(self, d: str) -> dict[str, float]:
        body: dict[str, Any] = {
            "startDate": f"{d}T00:00:00Z", "endDate": f"{d}T00:00:00Z", "timezone": "Asia/Seoul", "currency": "KRW",
            "dimensions": ["Day"], "format": "csv",
            "metrics": ["Displays", "Clicks", "AdvertiserCost", "SalesAllPc30d", "RevenueGeneratedAllPc30d"],
        }
        if self.advertiser_id:
            body["advertiserIds"] = self.advertiser_id
        r = requests.post(f"{HOST}/{self.version}/statistics/report", json=body,
                          headers={"Authorization": f"Bearer {self.token}", "Accept": "text/csv"}, timeout=60)
        if r.status_code in (401, 403):
            raise PermissionError(f"Criteo 권한 오류: {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"Criteo report {r.status_code}: {r.text[:300]}")
        agg = {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0}
        for row in csv.DictReader(io.StringIO(r.text)):
            agg["impressions"] += float(row.get("Displays") or 0)
            agg["clicks"] += float(row.get("Clicks") or 0)
            agg["ad_cost"] += float(row.get("AdvertiserCost") or 0)
            agg["conversions"] += float(row.get("SalesAllPc30d") or 0)
            agg["ad_revenue"] += float(row.get("RevenueGeneratedAllPc30d") or 0)
        return agg
