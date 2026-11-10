"""네이버 성과형 디스플레이 광고(GFA) API — 광고계정 일자별 성과 (무료). **네이버 로그인(OAuth 2.0)** 방식.

필요: NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (developers.naver.com 애플리케이션 — '네이버 로그인' API 사용 체크; 데이터랩과 같은 앱 공용)
      GFA_AD_ACCOUNT_NO (gfa.naver.com 광고계정 번호)   선택: GFA_MANAGER_ACCOUNT_NO (관리계정 멤버로만 권한이 있을 때)
권한: GFA 사이트 **대표 관리 계정 > 설정 > API 관리 > API 사용 신청** 에 Client ID 등록 → 네이버 관리자 승인 후 호출 가능.
토큰: 네이버 로그인 액세스 토큰(1시간) + 리프레시 토큰 — DB(app_kv)에 저장하고 자동 갱신. 최초 1회는 gfa-token 워크플로.
인가: GET https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id&redirect_uri&state=gfa
토큰: GET https://nid.naver.com/oauth2.0/token?grant_type=authorization_code|refresh_token&client_id&client_secret&code|refresh_token
성과: GET https://openapi.naver.com/v1/ad-api/1.0/adAccounts/{no}/performance/past/campaigns?startDate&endDate   (최대 31일, 2년 전~전일, 전일은 02시 이후)
      GET .../performance/conversion/past/campaigns  (convType=PURCHASE 를 구매 전환으로 집계)
필드: impCount 노출 · clickCount 클릭 · sales 광고비(네이버 매출 = 광고주 비용) · convCount/convSales 전환.
문서: https://naver-ad-api.github.io/developers/
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "GFA_AD_ACCOUNT_NO")
NID = "https://nid.naver.com/oauth2.0"
HOST = "https://openapi.naver.com/v1/ad-api/1.0"
KV_ACCESS, KV_REFRESH, KV_EXPIRES = "gfa_access_token", "gfa_refresh_token", "gfa_access_expires_at"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def authorize_url(client_id: str, redirect_uri: str) -> str:
    from urllib.parse import urlencode
    return f"{NID}/authorize?" + urlencode({"response_type": "code", "client_id": client_id,
                                            "redirect_uri": redirect_uri, "state": "gfa"})


def _token_call(params: dict[str, str]) -> dict[str, Any]:
    params = {"client_id": config.env("NAVER_CLIENT_ID"), "client_secret": config.env("NAVER_CLIENT_SECRET"), **params}
    r = requests.get(f"{NID}/token", params=params, timeout=30)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400 or body.get("error"):
        raise PermissionError(f"네이버 로그인 토큰 실패 {r.status_code}: {r.text[:300]}")
    return body


def exchange_code(code: str, state: str = "gfa") -> dict[str, Any]:
    return _token_call({"grant_type": "authorization_code", "code": code, "state": state})


def save_tokens(store, tok: dict[str, Any]) -> None:
    store.kv_set(KV_ACCESS, tok.get("access_token", ""))
    if tok.get("refresh_token"):
        store.kv_set(KV_REFRESH, tok["refresh_token"])
    store.kv_set(KV_EXPIRES, str(int(time.time()) + int(tok.get("expires_in", 3600)) - 120))


def _sum(rows: list[dict[str, Any]], key: str) -> float:
    return float(sum(float(r.get(key, 0) or 0) for r in rows))


class GfaClient:
    def __init__(self, store=None):
        self.store = store
        self.account_no = config.env("GFA_AD_ACCOUNT_NO")
        self.manager_no = config.env("GFA_MANAGER_ACCOUNT_NO")
        kv = (lambda k: store.kv_get(k)) if store is not None else (lambda k: "")
        self.access = kv(KV_ACCESS) or config.env("GFA_ACCESS_TOKEN")
        self.refresh = kv(KV_REFRESH) or config.env("GFA_REFRESH_TOKEN")
        self.expires_at = int(kv(KV_EXPIRES) or 0)
        if not (self.access or self.refresh):
            raise PermissionError("GFA 토큰 없음 → Actions 'gfa authorize url' → 'gfa token' 으로 최초 발급")

    def _refresh_now(self) -> None:
        if not self.refresh:
            raise PermissionError("GFA 리프레시 토큰 없음 → 재발급 필요 (gfa token 워크플로)")
        tok = _token_call({"grant_type": "refresh_token", "refresh_token": self.refresh})
        self.access = tok.get("access_token", self.access)
        self.refresh = tok.get("refresh_token", self.refresh)
        self.expires_at = int(time.time()) + int(tok.get("expires_in", 3600)) - 120
        if self.store is not None:
            save_tokens(self.store, tok)

    def _headers(self) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.access}"}
        if self.manager_no:
            h["AccessManagerAccountNo"] = self.manager_no
        return h

    def _get(self, path: str, params: dict[str, Any]) -> requests.Response:
        if not self.access or (self.expires_at and time.time() >= self.expires_at):
            self._refresh_now()
        r = requests.get(f"{HOST}{path}", headers=self._headers(), params=params, timeout=30)
        if r.status_code == 401 or (r.status_code == 403 and "024" in r.text):  # 인증 실패 코드 024 → 토큰 갱신 후 1회 재시도
            self._refresh_now()
            r = requests.get(f"{HOST}{path}", headers=self._headers(), params=params, timeout=30)
        return r

    def _rows(self, path: str, d: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        params: dict[str, Any] = {"startDate": d, "endDate": d, "limit": 1000}
        for _ in range(50):
            r = self._get(path, params)
            if r.status_code in (401, 403):
                raise PermissionError(f"GFA 권한 오류 {r.status_code}: {r.text[:200]} (API 사용 신청 승인 · 광고계정 멤버 · GFA_AD_ACCOUNT_NO 확인)")
            if r.status_code >= 400:
                raise RuntimeError(f"GFA {path} {r.status_code}: {r.text[:300]}")
            body = r.json()
            rows += body.get("rows", []) or []
            nxt = body.get("next")
            if not nxt:
                break
            params["next"] = nxt
        return rows

    def ad_accounts(self) -> list[dict[str, Any]]:
        r = self._get("/adAccounts", {"page": 0, "size": 100})
        if r.status_code >= 400:
            raise RuntimeError(f"GFA adAccounts {r.status_code}: {r.text[:300]}")
        body = r.json()
        return body.get("content") or body.get("rows") or (body if isinstance(body, list) else [])

    def daily(self, d: str) -> dict[str, float]:
        perf = self._rows(f"/adAccounts/{self.account_no}/performance/past/campaigns", d)
        agg = {"ad_cost": _sum(perf, "sales"), "impressions": _sum(perf, "impCount"), "clicks": _sum(perf, "clickCount"),
               "conversions": 0.0, "ad_revenue": 0.0}
        try:
            conv = self._rows(f"/adAccounts/{self.account_no}/performance/conversion/past/campaigns", d)
            buy = [r for r in conv if (r.get("convType") or "").upper() == "PURCHASE"]
            agg["conversions"], agg["ad_revenue"] = _sum(buy, "convCount"), _sum(buy, "convSales")
        except RuntimeError:  # 전환 추적 미설정 계정 — 기본 성과만 저장
            pass
        return agg
