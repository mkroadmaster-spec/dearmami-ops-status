"""카카오모먼트 광고 API — 광고계정 일자별 리포트 (무료).

필요: KAKAO_REST_API_KEY (developers.kakao.com 앱 키), KAKAO_AD_ACCOUNT_ID (moment.kakao.com 광고계정 번호)
선택: KAKAO_CLIENT_SECRET (앱의 '보안 > Client Secret' 을 켠 경우)
토큰: 카카오 로그인 액세스 토큰(6시간) + 리프레시 토큰(2개월) — DB(app_kv)에 저장하고 자동 갱신 (Secret 보다 DB 우선).
      최초 1회는 .github/workflows/kakao-token.yml 로 발급. 환경변수 KAKAO_ACCESS_TOKEN/KAKAO_REFRESH_TOKEN 도 폴백으로 읽음.
조건: 앱에 '카카오모먼트' 사용 신청 승인 + 로그인한 카카오계정이 그 광고계정의 멤버.
실 키로 첫 1회 응답 필드 검증 권장.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("KAKAO_REST_API_KEY", "KAKAO_AD_ACCOUNT_ID")
HOST = "https://apis.moment.kakao.com/openapi/v4"
KAUTH = "https://kauth.kakao.com/oauth"
KV_ACCESS, KV_REFRESH, KV_EXPIRES = "kakao_access_token", "kakao_refresh_token", "kakao_access_expires_at"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def authorize_url(rest_key: str, redirect_uri: str) -> str:
    from urllib.parse import urlencode
    return f"{KAUTH}/authorize?" + urlencode({"client_id": rest_key, "redirect_uri": redirect_uri,
                                               "response_type": "code", "state": "kakao"})


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    data = {"grant_type": "authorization_code", "client_id": config.env("KAKAO_REST_API_KEY"),
            "redirect_uri": redirect_uri, "code": code}
    if config.env("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = config.env("KAKAO_CLIENT_SECRET")
    r = requests.post(f"{KAUTH}/token", data=data, timeout=30)
    if r.status_code >= 400:
        raise PermissionError(f"카카오 토큰 교환 실패 {r.status_code}: {r.text[:300]}")
    return r.json()


def save_tokens(store, tok: dict[str, Any]) -> None:
    store.kv_set(KV_ACCESS, tok.get("access_token", ""))
    if tok.get("refresh_token"):
        store.kv_set(KV_REFRESH, tok["refresh_token"])
    store.kv_set(KV_EXPIRES, str(int(time.time()) + int(tok.get("expires_in", 21600)) - 300))


class KakaoMomentClient:
    def __init__(self, store=None):
        self.store = store
        self.account_id = config.env("KAKAO_AD_ACCOUNT_ID")
        kv = (lambda k: store.kv_get(k)) if store is not None else (lambda k: "")
        self.access = kv(KV_ACCESS) or config.env("KAKAO_ACCESS_TOKEN")
        self.refresh = kv(KV_REFRESH) or config.env("KAKAO_REFRESH_TOKEN")
        self.expires_at = int(kv(KV_EXPIRES) or 0)
        if not (self.access or self.refresh):
            raise PermissionError("카카오 토큰 없음 → Actions 'kakao authorize url' → 'kakao token' 으로 최초 발급")

    def _refresh_now(self) -> None:
        if not self.refresh:
            raise PermissionError("카카오 리프레시 토큰 없음 → 재발급 필요 (kakao token 워크플로)")
        data = {"grant_type": "refresh_token", "client_id": config.env("KAKAO_REST_API_KEY"), "refresh_token": self.refresh}
        if config.env("KAKAO_CLIENT_SECRET"):
            data["client_secret"] = config.env("KAKAO_CLIENT_SECRET")
        r = requests.post(f"{KAUTH}/token", data=data, timeout=30)
        if r.status_code >= 400:
            raise PermissionError(f"카카오 토큰 갱신 실패 {r.status_code}: {r.text[:200]} → 재발급 필요")
        tok = r.json()
        self.access = tok.get("access_token", self.access)
        self.refresh = tok.get("refresh_token", self.refresh)
        self.expires_at = int(time.time()) + int(tok.get("expires_in", 21600)) - 300
        if self.store is not None:
            save_tokens(self.store, tok)

    def _get(self, path: str, params: dict[str, Any]) -> requests.Response:
        if not self.access or (self.expires_at and time.time() >= self.expires_at):
            self._refresh_now()
        h = {"Authorization": f"Bearer {self.access}", "adAccountId": self.account_id}
        r = requests.get(f"{HOST}{path}", headers=h, params=params, timeout=30)
        if r.status_code == 401:
            self._refresh_now()
            h["Authorization"] = f"Bearer {self.access}"
            r = requests.get(f"{HOST}{path}", headers=h, params=params, timeout=30)
        return r

    def account_report(self, d: str) -> dict[str, float]:
        day = d.replace("-", "")
        r = self._get("/adAccounts/report", {"datePreset": "CUSTOM", "start": day, "end": day,
                                             "metricsGroup": "BASIC,PIXEL_SDK_CONVERSION"})
        if r.status_code in (401, 403):
            raise PermissionError(f"카카오 권한 오류: {r.text[:200]} (앱의 카카오모먼트 사용 승인 · 광고계정 멤버 여부 확인)")
        if r.status_code >= 400:
            raise RuntimeError(f"Kakao report {r.status_code}: {r.text[:300]}")
        agg = {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0}
        for row in r.json().get("data", []):
            m: dict[str, Any] = row.get("metrics", {})
            agg["ad_cost"] += float(m.get("cost", 0) or 0)
            agg["impressions"] += float(m.get("imp", 0) or 0)
            agg["clicks"] += float(m.get("click", 0) or 0)
            agg["conversions"] += float(m.get("conv_purchase_7d", 0) or m.get("conv_purchase_1d", 0) or 0)
            agg["ad_revenue"] += float(m.get("conv_purchase_p_7d", 0) or m.get("conv_purchase_p_1d", 0) or 0)
        return agg
