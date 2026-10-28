"""수집기 레지스트리 — 새 채널 추가 시 여기에 등록 + tests/test_pipeline.py 기대 집합 갱신."""
from __future__ import annotations

from typing import Any

from .. import config
from ..clients import ads_google, ads_kakao, ads_meta, ads_naver, cafe24_client, ga4 as ga4_client, naver_datalab, slack, telegram
from . import ads, cafe24, cafe24_analytics, competitor, creative, demo, ga4, naver_keyword
from .base import Collector


def _shop_is_cafe24() -> bool:
    return (config.sources()["shop"].get("platform") or "").lower() == "cafe24"


REGISTRY: list[Collector] = [
    Collector(name="cafe24", label="카페24 Admin API (매출·주문)", step="STEP 1",
              required_env=cafe24_client.REQUIRED_ENV, optional_env=("CAFE24_ACCESS_TOKEN", "CAFE24_REFRESH_TOKEN"),
              is_configured=lambda: _shop_is_cafe24() and cafe24_client.is_configured(),
              collect=cafe24.collect, demo=demo.cafe24, doc="docs/CONNECT-GUIDE.md#step-1", tab="카페24 어드민"),
    Collector(name="cafe24_analytics", label="카페24 통계 API (접속통계 9블록)", step="STEP 1",
              required_env=cafe24_client.REQUIRED_ENV,
              is_configured=lambda: _shop_is_cafe24() and cafe24_client.is_configured(),
              collect=cafe24_analytics.collect, demo=demo.cafe24_analytics,
              doc="skills/카페24-운영현황 (mall.read_analytics scope 필수)", tab="카페24 어드민"),
    Collector(name="ga4", label="GA4 (방문자·전환·사이트 분석)", step="STEP 2",
              required_env=ga4_client.REQUIRED_ENV, is_configured=ga4_client.is_configured,
              collect=ga4.collect, demo=demo.ga4, doc="docs/GA4-SETUP.md", tab="카페24 어드민",
              sources=ga4.SOURCES),
    Collector(name="ads", label="광고 (Meta·네이버SA·카카오·구글)", step="STEP 3~7",
              required_env=(), is_configured=ads.is_configured,
              collect=ads.collect, demo=demo.ads, doc="docs/CONNECT-GUIDE.md#step-2", tab="광고"),
    Collector(name="creative", label="Meta 소재 (광고 히스토리)", step="STEP 3",
              required_env=ads_meta.REQUIRED_ENV, is_configured=creative.is_configured,
              collect=creative.collect, demo=demo.creative, doc="docs/CONNECT-GUIDE.md#step-2", tab="광고 히스토리"),
    Collector(name="naver_keyword", label="네이버 키워드·플레이스 (광고 히스토리)", step="STEP 4",
              required_env=ads_naver.REQUIRED_ENV, is_configured=naver_keyword.is_configured,
              collect=naver_keyword.collect, demo=demo.naver_keyword, doc="docs/CONNECT-GUIDE.md#step-4",
              tab="광고 히스토리", sources=naver_keyword.SOURCES),
    Collector(name="competitor", label="네이버 데이터랩 (경쟁사 트렌드)", step="STEP 5",
              required_env=naver_datalab.REQUIRED_ENV, is_configured=naver_datalab.is_configured,
              collect=competitor.collect, demo=demo.competitor, doc="docs/CONNECT-GUIDE.md#step-3", tab="광고"),
]

# 광고 하위 채널 — 화면의 '채널 연결' 탭에 개별 표시
AD_CHANNELS: list[dict[str, Any]] = [
    {"key": "meta", "label": "Meta 광고", "step": "STEP 3", "required_env": ads_meta.REQUIRED_ENV,
     "optional_env": ("META_APP_ID", "META_APP_SECRET"), "is_configured": ads_meta.is_configured,
     "doc": "docs/CONNECT-GUIDE.md#step-2"},
    {"key": "naver_sa", "label": "네이버 검색광고 (파워링크/플레이스)", "step": "STEP 4",
     "required_env": ads_naver.REQUIRED_ENV, "optional_env": (), "is_configured": ads_naver.is_configured,
     "doc": "docs/CONNECT-GUIDE.md#step-4"},
    {"key": "kakao", "label": "카카오모먼트", "step": "STEP 6", "required_env": ads_kakao.REQUIRED_ENV,
     "optional_env": (), "is_configured": ads_kakao.is_configured, "doc": "docs/CONNECT-GUIDE.md#step-5"},
    {"key": "google", "label": "Google Ads", "step": "STEP 7", "required_env": ads_google.REQUIRED_ENV,
     "optional_env": ("GOOGLE_ADS_LOGIN_CUSTOMER_ID",), "is_configured": ads_google.is_configured,
     "doc": "docs/CONNECT-GUIDE.md#step-6"},
]

NOTIFY_CHANNELS = [
    {"key": "telegram", "label": "텔레그램 알림 (브리핑 + 대시보드 링크, PC·모바일)", "step": "STEP 8", "required_env": telegram.REQUIRED_ENV,
     "optional_env": ("DASHBOARD_URL",), "is_configured": telegram.is_configured, "doc": "docs/SETUP-GUIDE.md#step-8"},
    {"key": "slack", "label": "Slack 알림 (선택)", "step": "STEP 8", "required_env": slack.REQUIRED_ENV,
     "optional_env": (), "is_configured": slack.is_configured, "doc": "docs/CONNECT-GUIDE.md#step-7"},
]


def _env_state(names: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{"name": n, "set": bool(config.env(n))} for n in names]


def channel_status(store=None) -> list[dict[str, Any]]:
    """채널 연결 상태 — 대시보드 '채널 연결' 탭 + /api/channels."""
    last = store.last_status_by_source() if store is not None else {}
    mode = config.mode()
    items: list[dict[str, Any]] = []
    for c in REGISTRY:
        if c.name in ("ads", "creative", "naver_keyword"):
            continue  # 하위 채널 카드로 표시
        items.append({"key": c.name, "label": c.label, "step": c.step, "tab": c.tab, "doc": c.doc,
                      "configured": bool(c.is_configured()),
                      "env": _env_state(c.required_env), "optional_env": _env_state(c.optional_env),
                      "last": last.get(c.name), "mode": mode})
    for ch in AD_CHANNELS:
        extra = {"meta": " + 소재 히스토리", "naver_sa": " + 키워드·플레이스 히스토리"}.get(ch["key"], "")
        items.append({"key": ch["key"], "label": ch["label"] + extra, "step": ch["step"], "tab": "광고", "doc": ch["doc"],
                      "configured": bool(ch["is_configured"]()),
                      "env": _env_state(ch["required_env"]), "optional_env": _env_state(ch["optional_env"]),
                      "last": last.get("ads"), "mode": mode})
    for nc in NOTIFY_CHANNELS:
        items.append({"key": nc["key"], "label": nc["label"], "step": nc["step"], "tab": "알림", "doc": nc["doc"],
                      "configured": bool(nc["is_configured"]()),
                      "env": _env_state(nc["required_env"]), "optional_env": _env_state(nc["optional_env"]), "last": None, "mode": mode})
    return items
