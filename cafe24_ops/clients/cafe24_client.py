"""카페24 Admin API 클라이언트 (OAuth2 + 토큰 회전 영속).

⚠ refresh_token 은 갱신마다 회전하고 직전 것이 즉시 무효.
   토큰을 쓰는 모든 곳은 반드시 `Cafe24Client.from_store(store)` 를 사용 —
   갱신되는 그 순간 app_kv 에 되쓴다. (docs/NEW-CLIENT-CHECKLIST.md §6)
"""
from __future__ import annotations

import base64
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .. import config

SCOPES = [
    "mall.read_order", "mall.read_customer", "mall.read_community",
    "mall.read_product", "mall.read_category", "mall.read_application",
    "mall.read_analytics",
]
REQUIRED_ENV = ("CAFE24_MALL_ID", "CAFE24_CLIENT_ID", "CAFE24_CLIENT_SECRET")

KV_ACCESS = "cafe24_access_token"
KV_REFRESH = "cafe24_refresh_token"
KV_SCOPES = "cafe24_token_scopes"
KV_EXPIRES = "cafe24_access_expires_at"


class Cafe24AuthError(RuntimeError):
    pass


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def base_url(mall_id: str) -> str:
    return f"https://{mall_id}.cafe24api.com/api/v2"


def authorize_url(mall_id: str, client_id: str, redirect_uri: str, state: str = "ops") -> str:
    q = {
        "response_type": "code", "client_id": client_id, "state": state,
        "redirect_uri": redirect_uri, "scope": ",".join(SCOPES),
    }
    return f"{base_url(mall_id)}/oauth/authorize?{urlencode(q)}"


def _basic(client_id: str, client_secret: str) -> str:
    return "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


def exchange_code(mall_id: str, client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict[str, Any]:
    r = requests.post(
        f"{base_url(mall_id)}/oauth/token",
        headers={"Authorization": _basic(client_id, client_secret),
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        timeout=30,
    )
    if r.status_code != 200:
        raise Cafe24AuthError(f"token exchange failed {r.status_code}: {r.text[:300]}")
    return r.json()


def refresh_token(mall_id: str, client_id: str, client_secret: str, refresh: str) -> dict[str, Any]:
    r = requests.post(
        f"{base_url(mall_id)}/oauth/token",
        headers={"Authorization": _basic(client_id, client_secret),
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=30,
    )
    if r.status_code != 200:
        raise Cafe24AuthError(f"token refresh failed {r.status_code}: {r.text[:300]}")
    return r.json()


def save_tokens(store, tok: dict[str, Any]) -> None:
    """토큰 응답을 즉시 DB 에 저장 (회전분 유실 방지)."""
    store.kv_set(KV_ACCESS, tok.get("access_token", ""))
    if tok.get("refresh_token"):
        store.kv_set(KV_REFRESH, tok["refresh_token"])
    scopes = tok.get("scopes") or tok.get("scope") or []
    if isinstance(scopes, list):
        scopes = ",".join(scopes)
    if scopes:
        store.kv_set(KV_SCOPES, str(scopes))
    # access 2시간: 여유 5분
    store.kv_set(KV_EXPIRES, str(int(time.time()) + int(tok.get("expires_in", 7200)) - 300))


def missing_scopes(granted: str) -> list[str]:
    have = {s.strip() for s in (granted or "").replace(" ", ",").split(",") if s.strip()}
    return [s for s in SCOPES if s not in have]


class Cafe24Client:
    def __init__(self, mall_id: str, client_id: str, client_secret: str,
                 access_token: str, refresh: str, store=None, api_version: str = "2025-06-01",
                 expires_at: int = 0):
        self.mall_id = mall_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh = refresh
        self.store = store
        self.api_version = api_version
        self.expires_at = expires_at
        self.session = requests.Session()

    @classmethod
    def from_store(cls, store) -> "Cafe24Client":
        """DB(app_kv) 토큰 우선, 없으면 환경변수. 갱신 시 DB 에 되쓴다."""
        if not is_configured():
            raise Cafe24AuthError("CAFE24_MALL_ID/CLIENT_ID/CLIENT_SECRET 미설정")
        src = config.sources()["shop"]
        access = store.kv_get(KV_ACCESS) or config.env("CAFE24_ACCESS_TOKEN")
        refresh = store.kv_get(KV_REFRESH) or config.env("CAFE24_REFRESH_TOKEN")
        if not refresh and not access:
            raise Cafe24AuthError("카페24 토큰 없음 → scripts/cafe24_auth.py 로 최초 발급")
        exp = int(store.kv_get(KV_EXPIRES, "0") or 0)
        return cls(src["mall_id"], config.env("CAFE24_CLIENT_ID"), config.env("CAFE24_CLIENT_SECRET"),
                   access, refresh, store=store, api_version=src.get("api_version", "2025-06-01"),
                   expires_at=exp)

    # ---- token -----------------------------------------------------------
    def _refresh_now(self) -> None:
        if not self.refresh:
            raise Cafe24AuthError("refresh_token 없음 → 재인증 필요")
        tok = refresh_token(self.mall_id, self.client_id, self.client_secret, self.refresh)
        self.access_token = tok.get("access_token", "")
        self.refresh = tok.get("refresh_token", self.refresh)
        self.expires_at = int(time.time()) + int(tok.get("expires_in", 7200)) - 300
        if self.store is not None:
            save_tokens(self.store, tok)  # 즉시 되쓰기

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Cafe24-Api-Version": self.api_version}

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.expires_at and time.time() >= self.expires_at:
            self._refresh_now()
        url = f"{base_url(self.mall_id)}{path}"
        r = self.session.get(url, headers=self._headers(), params=params, timeout=30)
        if r.status_code == 401:
            self._refresh_now()
            r = self.session.get(url, headers=self._headers(), params=params, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"cafe24 GET {path} {r.status_code}: {r.text[:300]}")
        return r.json()

    # ---- endpoints -------------------------------------------------------
    def orders(self, start_date: str, end_date: str, **extra) -> list[dict[str, Any]]:
        """주문 목록 전체(페이지네이션). 기본 결제완료 이상, 취소 제외는 호출측에서 판단."""
        out: list[dict[str, Any]] = []
        offset, limit = 0, 1000
        while True:
            params = {"start_date": start_date, "end_date": end_date, "limit": limit,
                      "offset": offset, "date_type": "pay_date", **extra}
            data = self.get("/admin/orders", params)
            chunk = data.get("orders", [])
            out.extend(chunk)
            if len(chunk) < limit or offset > 8000:
                break
            offset += limit
        return out

    def orders_count(self, start_date: str, end_date: str) -> int:
        data = self.get("/admin/orders/count", {"start_date": start_date, "end_date": end_date,
                                                "date_type": "pay_date"})
        return int(data.get("count", 0))

    def products(self, limit: int = 100, offset: int = 0, **extra) -> list[dict[str, Any]]:
        return self.get("/admin/products", {"limit": limit, "offset": offset, **extra}).get("products", [])

    def products_count(self, **params) -> int:
        return int(self.get("/admin/products/count", params).get("count", 0))

    def boards_articles_count(self, board_no: int, start_date: str, end_date: str) -> int:
        """후기 등 게시판 글 수 (mall.read_community)."""
        data = self.get(f"/admin/boards/{board_no}/articles/count",
                        {"start_date": start_date, "end_date": end_date})
        return int(data.get("count", 0))
