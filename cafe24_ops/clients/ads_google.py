"""Google Ads API (REST searchStream) — 고객 계정 일자별 성과. 무료.

필요: GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID(대시 없는 10자리), GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET
선택: GOOGLE_ADS_LOGIN_CUSTOMER_ID (관리자/MCC 계정 ID)
토큰: OAuth 리프레시 토큰을 DB(app_kv)에 저장하고 액세스 토큰(1시간)을 자동 갱신.
      최초 1회는 .github/workflows/google-authorize-url.yml → google-token.yml. 환경변수 GOOGLE_ADS_REFRESH_TOKEN / GOOGLE_ADS_ACCESS_TOKEN 폴백.
조건: Cloud 프로젝트에서 Google Ads API 사용 설정 + 액세스 수준 '탐색자(Explorer)' 이상 + OAuth 클라이언트(웹) 리디렉션 URI 등록
      + 인가 시 로그인한 구글 계정이 광고계정(또는 관리자 계정) 접근 권한 보유.
"""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import requests

from .. import config

REQUIRED_ENV = ("GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET")
_ok_version = [""]
BASE = "https://googleads.googleapis.com"
# 구글은 메이저 버전을 약 1년 뒤 종료(종료된 버전은 404 HTML) → 설정 버전이 404 면 다음 후보로 자동 전환
VERSIONS = ("v25", "v26", "v24", "v23", "v27", "v28")
OAUTH_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/adwords"
KV_ACCESS, KV_REFRESH, KV_EXPIRES = "google_ads_access_token", "google_ads_refresh_token", "google_ads_access_expires_at"


def is_configured() -> bool:
    legacy = config.env_all("GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_ACCESS_TOKEN")
    return config.env_all(*REQUIRED_ENV) or legacy


def authorize_url(client_id: str, redirect_uri: str) -> str:
    return OAUTH_AUTH + "?" + urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
                                         "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": "google"})


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    r = requests.post(OAUTH_TOKEN, data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                                         "client_id": config.env("GOOGLE_ADS_CLIENT_ID"), "client_secret": config.env("GOOGLE_ADS_CLIENT_SECRET")}, timeout=30)
    if r.status_code >= 400:
        raise PermissionError(f"구글 토큰 교환 실패 {r.status_code}: {r.text[:300]}")
    return r.json()


def save_tokens(store, tok: dict[str, Any]) -> None:
    store.kv_set(KV_ACCESS, tok.get("access_token", ""))
    if tok.get("refresh_token"):
        store.kv_set(KV_REFRESH, tok["refresh_token"])
    store.kv_set(KV_EXPIRES, str(int(time.time()) + int(tok.get("expires_in", 3600)) - 120))


class GoogleAdsClient:
    def __init__(self, store=None):
        self.store = store
        self.dev_token = config.env("GOOGLE_ADS_DEVELOPER_TOKEN")
        self.customer_id = "".join(c for c in config.env("GOOGLE_ADS_CUSTOMER_ID") if c.isdigit())
        self.login_customer_id = "".join(c for c in config.env("GOOGLE_ADS_LOGIN_CUSTOMER_ID") if c.isdigit())
        kv = (lambda k: store.kv_get(k)) if store is not None else (lambda k: "")
        self.access = kv(KV_ACCESS) or config.env("GOOGLE_ADS_ACCESS_TOKEN")
        self.refresh = kv(KV_REFRESH) or config.env("GOOGLE_ADS_REFRESH_TOKEN")
        self.expires_at = int(kv(KV_EXPIRES) or 0)
        if not (self.access or self.refresh):
            raise PermissionError("구글 토큰 없음 → Actions 'google authorize url' → 'google token' 으로 최초 발급")

    def _refresh_now(self) -> None:
        if not self.refresh:
            raise PermissionError("구글 리프레시 토큰 없음 → 재발급 필요 (google token 워크플로)")
        r = requests.post(OAUTH_TOKEN, data={"grant_type": "refresh_token", "refresh_token": self.refresh,
                                             "client_id": config.env("GOOGLE_ADS_CLIENT_ID"), "client_secret": config.env("GOOGLE_ADS_CLIENT_SECRET")}, timeout=30)
        if r.status_code >= 400:
            raise PermissionError(f"구글 토큰 갱신 실패 {r.status_code}: {r.text[:200]} → 재발급 필요")
        tok = r.json()
        self.access = tok.get("access_token", self.access)
        self.expires_at = int(time.time()) + int(tok.get("expires_in", 3600)) - 120
        if self.store is not None:
            save_tokens(self.store, tok)

    def _headers(self) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.access}", "developer-token": self.dev_token, "Content-Type": "application/json"}
        if self.login_customer_id:
            h["login-customer-id"] = self.login_customer_id
        return h

    def search(self, query: str) -> list[dict[str, Any]]:
        """GAQL 조회 → 결과 행 목록 (버전 자동 전환·토큰 갱신 포함)."""
        if self.refresh and (not self.access or (self.expires_at and time.time() >= self.expires_at)):
            self._refresh_now()
        r = None
        for ver in dict.fromkeys([v for v in (config.env("GOOGLE_ADS_API_VERSION"), _ok_version[0]) if v] + list(VERSIONS)):
            url = f"{BASE}/{ver}/customers/{self.customer_id}/googleAds:searchStream"
            r = requests.post(url, headers=self._headers(), json={"query": query}, timeout=60)
            if r.status_code == 401 and self.refresh:
                self._refresh_now()
                r = requests.post(url, headers=self._headers(), json={"query": query}, timeout=60)
            if r.status_code == 404 and "json" not in r.headers.get("content-type", ""):
                continue  # 종료된(또는 아직 없는) API 버전 → 다음 후보
            _ok_version[0] = ver
            break
        if r.status_code in (401, 403):
            raise PermissionError(f"Google Ads 토큰/권한 오류 {r.status_code}: {r.text[:300]} (개발자 토큰 액세스 수준·login-customer-id·계정 권한 확인)")
        if r.status_code >= 400:
            raise RuntimeError(f"Google Ads {r.status_code}: {r.text[:500]}")
        return [row for batch in r.json() for row in batch.get("results", [])]

    def daily(self, d: str) -> dict[str, float]:
        query = ("SELECT metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions, "
                 f"metrics.conversions_value FROM customer WHERE segments.date = '{d}'")
        agg = {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0}
        for row in self.search(query):
            m = row.get("metrics", {})
            agg["ad_cost"] += float(m.get("costMicros", 0)) / 1_000_000
            agg["impressions"] += float(m.get("impressions", 0))
            agg["clicks"] += float(m.get("clicks", 0))
            agg["conversions"] += float(m.get("conversions", 0))
            agg["ad_revenue"] += float(m.get("conversionsValue", 0))
        return agg
