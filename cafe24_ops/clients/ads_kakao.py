"""카카오모먼트 광고 API — 광고계정 일자별 리포트 (무료). **비즈니스 인증(Business Auth)** 방식.

필요: KAKAO_REST_API_KEY (앱 REST API 키), KAKAO_AD_ACCOUNT_ID (moment.kakao.com 광고계정 번호)
      KAKAO_BUSINESS_SECRET (REST API 키 수정 화면의 클라이언트 시크릿 중 **'비즈니스 인증' 줄** 코드; 활성화 ON 이면 필수)
토큰: 비즈니스 토큰(액세스 6시간 + 리프레시) — DB(app_kv)에 저장하고 자동 갱신. 최초 1회는 kakao-authorize-url → kakao-token 워크플로.
조건: 비즈 앱 + 앱 소유자 본인인증 + [추가 기능 신청] 카카오모먼트 API 권한 승인 + [비즈니스 인증 > 동의항목] moment 항목 사용
      + 인가 시 로그인한 카카오계정이 광고계정 멤버. 리다이렉트 URI 는 [비즈니스 인증 리다이렉트 URI] 에 등록.
인가: GET https://kauth.kakao.com/oauth/business/authorize?client_id&redirect_uri&response_type=code&scope=moment_management&resource_ids=moment:<광고계정>
토큰: POST https://kauth.kakao.com/oauth/business/token (grant_type=authorization_code|refresh_token, client_secret)
리포트: GET /openapi/v4/adAccounts/report (header adAccountId, level=AD_ACCOUNT, start/end, metricsGroup) — 5초당 1회 제한.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("KAKAO_REST_API_KEY", "KAKAO_AD_ACCOUNT_ID")
HOST = "https://apis.moment.kakao.com/openapi/v4"
KAUTH = "https://kauth.kakao.com/oauth/business"
_last_call = [0.0]
KV_ACCESS, KV_REFRESH, KV_EXPIRES = "kakao_access_token", "kakao_refresh_token", "kakao_access_expires_at"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def _secret() -> str:
    return config.env("KAKAO_BUSINESS_SECRET") or config.env("KAKAO_CLIENT_SECRET")


def authorize_url(rest_key: str, redirect_uri: str, ad_account_id: str = "") -> str:
    """resource_ids 를 비우면 사용자가 동의 화면에서 광고계정을 직접 선택 (ID 가 틀리면 KOE234 → 비우는 쪽이 안전)."""
    from urllib.parse import urlencode
    q = {"client_id": rest_key, "redirect_uri": redirect_uri, "response_type": "code",
         "scope": "moment_management", "state": "kakao"}
    if ad_account_id:
        q["resource_ids"] = f"moment:{ad_account_id}"
    return f"{KAUTH}/authorize?" + urlencode(q)


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    data = {"grant_type": "authorization_code", "client_id": config.env("KAKAO_REST_API_KEY"),
            "redirect_uri": redirect_uri, "code": code}
    if _secret():
        data["client_secret"] = _secret()
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
        if _secret():
            data["client_secret"] = _secret()
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
        wait = 5.2 - (time.time() - _last_call[0])  # 리포트 API 5초당 1회
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        r = requests.get(f"{HOST}{path}", headers=h, params=params, timeout=30)
        if r.status_code == 401:
            self._refresh_now()
            h["Authorization"] = f"Bearer {self.access}"
            r = requests.get(f"{HOST}{path}", headers=h, params=params, timeout=30)
        return r

    def account_report(self, d: str) -> dict[str, float]:
        day = d.replace("-", "")
        r = self._get("/adAccounts/report", {"level": "AD_ACCOUNT", "start": day, "end": day,
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
