"""카카오모먼트 광고 API — 광고계정 일자별 리포트.

필요: KAKAO_ACCESS_TOKEN(모먼트 scope OAuth 토큰), KAKAO_AD_ACCOUNT_ID
주의: 액세스 토큰이 단기 만료 → 만료 시 재발급 필요(리프레시 자동화는 추후). 실 키로 첫 1회 응답 필드 검증 권장.
"""
from __future__ import annotations

from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("KAKAO_ACCESS_TOKEN", "KAKAO_AD_ACCOUNT_ID")
HOST = "https://apis.moment.kakao.com/openapi/v4"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


class KakaoMomentClient:
    def __init__(self):
        self.token = config.env("KAKAO_ACCESS_TOKEN")
        self.account_id = config.env("KAKAO_AD_ACCOUNT_ID")

    def account_report(self, d: str) -> dict[str, float]:
        r = requests.get(f"{HOST}/adAccounts/report", headers={
            "Authorization": f"Bearer {self.token}", "adAccountId": self.account_id,
        }, params={"datePreset": "CUSTOM", "start": d.replace("-", ""), "end": d.replace("-", ""),
                   "metricsGroup": "BASIC,PIXEL_SDK_CONVERSION"}, timeout=30)
        if r.status_code in (401, 403):
            raise PermissionError(f"Kakao 토큰 만료/권한 없음: {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"Kakao report {r.status_code}: {r.text[:300]}")
        agg = {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0}
        for row in r.json().get("data", []):
            m: dict[str, Any] = row.get("metrics", {})
            agg["ad_cost"] += float(m.get("cost", 0))
            agg["impressions"] += float(m.get("imp", 0))
            agg["clicks"] += float(m.get("click", 0))
            agg["conversions"] += float(m.get("conv_purchase_1d", 0) or m.get("conv_purchase_7d", 0))
            agg["ad_revenue"] += float(m.get("conv_purchase_p_1d", 0) or m.get("conv_purchase_p_7d", 0))
        return agg
