"""Google Ads API (REST searchStream) — 고객 계정 일자별 성과.

필요: GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_ACCESS_TOKEN, GOOGLE_ADS_CUSTOMER_ID(대시 없는 10자리)
선택: GOOGLE_ADS_LOGIN_CUSTOMER_ID (MCC)
주의: 개발자 토큰 운영 승인에 수일. access 토큰 단기 만료(refresh 자동갱신 미구현). 다른 채널 먼저 켜고 나중에.
"""
from __future__ import annotations

import requests

from .. import config

REQUIRED_ENV = ("GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_ACCESS_TOKEN", "GOOGLE_ADS_CUSTOMER_ID")
HOST = "https://googleads.googleapis.com/v18"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


class GoogleAdsClient:
    def __init__(self):
        self.dev_token = config.env("GOOGLE_ADS_DEVELOPER_TOKEN")
        self.token = config.env("GOOGLE_ADS_ACCESS_TOKEN")
        self.customer_id = config.env("GOOGLE_ADS_CUSTOMER_ID").replace("-", "")
        self.login_customer_id = config.env("GOOGLE_ADS_LOGIN_CUSTOMER_ID").replace("-", "")

    def daily(self, d: str) -> dict[str, float]:
        headers = {"Authorization": f"Bearer {self.token}", "developer-token": self.dev_token,
                   "Content-Type": "application/json"}
        if self.login_customer_id:
            headers["login-customer-id"] = self.login_customer_id
        query = ("SELECT metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions, "
                 f"metrics.conversions_value FROM customer WHERE segments.date = '{d}'")
        r = requests.post(f"{HOST}/customers/{self.customer_id}/googleAds:searchStream",
                          headers=headers, json={"query": query}, timeout=30)
        if r.status_code in (401, 403):
            raise PermissionError(f"Google Ads 토큰/권한 오류: {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"Google Ads {r.status_code}: {r.text[:300]}")
        agg = {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0}
        for batch in r.json():
            for row in batch.get("results", []):
                m = row.get("metrics", {})
                agg["ad_cost"] += float(m.get("costMicros", 0)) / 1_000_000
                agg["impressions"] += float(m.get("impressions", 0))
                agg["clicks"] += float(m.get("clicks", 0))
                agg["conversions"] += float(m.get("conversions", 0))
                agg["ad_revenue"] += float(m.get("conversionsValue", 0))
        return agg
