"""Meta Marketing API — 계정 레벨 + 광고(소재) 레벨 인사이트.

필요: META_ACCESS_TOKEN(시스템 사용자 토큰 — 만료 없음 권장), META_AD_ACCOUNT_ID(act_ 뒤 숫자)
선택: META_APP_ID/META_APP_SECRET → 사용자 토큰(60일)일 때 장기토큰 교환 후 app_kv 영속
함정: 그래프 탐색기 사용자 토큰은 60일 만료 → 401 code=190 → 36일 결측 사고. 시스템 사용자 토큰 + Slack 알림.
전환: 계정·소재 레벨 모두 `_conversions()` 로 통일 (리드젠은 RESULT_ACTION_TYPES 합산, 없을 때만 구매 폴백).
"""
from __future__ import annotations

from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID")
GRAPH = "https://graph.facebook.com/v21.0"
KV_TOKEN = "meta_access_token"

PURCHASE_TYPES = ("omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase")
# 리드젠 업체용 '결과' 액션 (구매 없는 상담·문의형) — sources.yaml `lead_gen: true` 일 때 우선
RESULT_ACTION_TYPES = ("complete_registration", "lead", "submit_application", "contact",
                       "onsite_conversion.messaging_conversation_started_7d", "onsite_conversion.lead_grouped")
INSIGHT_FIELDS = "spend,impressions,clicks,reach,frequency,actions,action_values"


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def _action_sum(actions: list[dict[str, Any]] | None, types: tuple[str, ...]) -> float:
    by = {a.get("action_type"): float(a.get("value", 0)) for a in actions or []}
    for t in types:
        if t in by:
            return by[t]
    return 0.0


def _action_sum_suffix(actions: list[dict[str, Any]] | None, suffixes: tuple[str, ...]) -> float:
    """ad-level 은 통합 이름 없이 픽셀 원시 이름(offsite_conversion.fb_pixel_complete_registration 등)만 줄 수 있다."""
    return sum(float(a.get("value", 0)) for a in actions or []
               if any(str(a.get("action_type", "")).endswith(s) for s in suffixes))


def _conversions(actions: list[dict[str, Any]] | None) -> float:
    lead_gen = bool(config.sources().get("lead_gen"))
    if lead_gen:
        v = sum(_action_sum(actions, (t,)) for t in RESULT_ACTION_TYPES)
        if not v:
            v = _action_sum_suffix(actions, tuple(t.split(".")[-1] for t in RESULT_ACTION_TYPES))
        if v:
            return v
    return _action_sum(actions, PURCHASE_TYPES)


def _metrics(row: dict[str, Any]) -> dict[str, float]:
    return {"ad_cost": float(row.get("spend", 0)), "impressions": float(row.get("impressions", 0)),
            "clicks": float(row.get("clicks", 0)), "reach": float(row.get("reach", 0) or 0),
            "frequency": float(row.get("frequency", 0) or 0),
            "conversions": _conversions(row.get("actions")), "ad_revenue": _action_sum(row.get("action_values"), PURCHASE_TYPES)}


class MetaAdsClient:
    def __init__(self, store=None):
        self.store = store
        self.token = (store.kv_get(KV_TOKEN) if store is not None else "") or config.env("META_ACCESS_TOKEN")
        acc = config.env("META_AD_ACCOUNT_ID")
        self.account_id = acc if acc.startswith("act_") else f"act_{acc}"

    def _get(self, path: str, **params) -> dict[str, Any]:
        r = requests.get(f"{GRAPH}/{path}", params={"access_token": self.token, **params}, timeout=60)
        if r.status_code == 401 or (r.status_code == 400 and '"code":190' in r.text):
            raise PermissionError(f"Meta 토큰 만료/무효(code=190): {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"Meta {path} {r.status_code}: {r.text[:300]}")
        return r.json()

    def try_extend_token(self) -> str:
        app_id, app_secret = config.env("META_APP_ID"), config.env("META_APP_SECRET")
        if not (app_id and app_secret):
            return "skip"
        r = requests.get(f"{GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": app_secret, "fb_exchange_token": self.token}, timeout=30)
        if r.status_code != 200:
            return f"갱신 실패 — 기존 토큰으로 진행 ({r.status_code})"
        tok = r.json().get("access_token")
        if tok:
            self.token = tok
            if self.store is not None:
                self.store.kv_set(KV_TOKEN, tok)
        return "장기토큰 갱신 OK"

    def account_insights(self, d: str) -> dict[str, float]:
        rows = self._get(f"{self.account_id}/insights", level="account", fields=INSIGHT_FIELDS,
                         time_range=f'{{"since":"{d}","until":"{d}"}}').get("data", [])
        return _metrics(rows[0]) if rows else _metrics({})

    def ad_insights(self, d: str) -> list[dict[str, Any]]:
        """광고(소재) 레벨 — 활성/최근 활성만 유의미. 한 페이지 500."""
        out = []
        data = self._get(f"{self.account_id}/insights", level="ad", limit=500,
                         fields="ad_id,ad_name,campaign_name,adset_name," + INSIGHT_FIELDS,
                         time_range=f'{{"since":"{d}","until":"{d}"}}')
        for row in data.get("data", []):
            out.append({"ad_id": row.get("ad_id"), "ad_name": row.get("ad_name", ""),
                        "campaign": row.get("campaign_name", ""), "adset": row.get("adset_name", ""), **_metrics(row)})
        return out

    def creatives(self, ad_ids: list[str]) -> dict[str, dict[str, str]]:
        """ad_id → {thumbnail_url, image_url}"""
        out: dict[str, dict[str, str]] = {}
        if not ad_ids:
            return out
        data = self._get(f"{self.account_id}/ads", limit=500, fields="id,creative{thumbnail_url,image_url}",
                         filtering=f'[{{"field":"ad.id","operator":"IN","value":{list(ad_ids)!r}}}]'.replace("'", '"'))
        for a in data.get("data", []):
            cr = a.get("creative") or {}
            out[a["id"]] = {"thumbnail_url": cr.get("thumbnail_url", ""), "image_url": cr.get("image_url", "")}
        return out
