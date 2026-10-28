"""네이버 검색광고 키워드(파워링크) + 플레이스 광고그룹 수집기 — 광고 히스토리 탭.
source='naver_keyword' / 'naver_place'."""
from __future__ import annotations

from ..clients import ads_naver
from .base import Fact, PartialFailure, fact

SOURCES = ("naver_keyword", "naver_place")
METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")


def is_configured() -> bool:
    return ads_naver.is_configured()


def collect(store, d: str) -> list[Fact]:
    c = ads_naver.NaverSAClient()
    out: list[Fact] = []
    errors = []
    try:
        for r in c.keyword_stats(d):
            if r["impressions"] <= 0:
                continue
            dims = {"keyword_id": r["keyword_id"], "keyword": r["keyword"], "adgroup": r["adgroup"], "campaign": r["campaign"]}
            out += [fact(d, "naver_keyword", k, r[k], **dims) for k in METRICS]
    except Exception as e:  # noqa: BLE001
        errors.append(f"keywords: {e}")
    try:
        for r in c.place_adgroup_stats(d):
            dims = {"adgroup_id": r["adgroup_id"], "adgroup": r["adgroup"], "campaign": r["campaign"]}
            out += [fact(d, "naver_place", k, r[k], **dims) for k in METRICS]
    except Exception as e:  # noqa: BLE001
        errors.append(f"place: {e}")
    if errors and not out:
        raise RuntimeError("naver_keyword 전부 실패: " + " | ".join(errors))
    if errors:
        raise PartialFailure(out, errors)
    return out
