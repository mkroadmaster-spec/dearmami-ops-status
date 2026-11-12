"""네이버 검색광고 키워드(파워링크) + 플레이스 광고그룹 수집기 — 광고 히스토리 탭.
source='naver_keyword' / 'naver_place'."""
from __future__ import annotations

from ..clients import ads_naver
from .base import Fact, PartialFailure, fact

SOURCES = ("naver_keyword", "naver_place")
METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")
TOP_KEYWORDS = 60  # 하루 비용 상위 키워드만 (2025-01~ 누적 시 DB 512MB 한도 고려)


def is_configured() -> bool:
    return ads_naver.is_configured()


def collect(store, d: str) -> list[Fact]:
    c = ads_naver.NaverSAClient()
    out: list[Fact] = []
    errors = []
    try:
        rows = [r for r in c.keyword_stats(d) if r["impressions"] > 0]
        rows.sort(key=lambda r: (-r["ad_cost"], -r["clicks"], -r["impressions"]))
        for r in rows[:TOP_KEYWORDS]:
            dims = {"keyword_id": r["keyword_id"], "keyword": r["keyword"], "adgroup": r["adgroup"], "campaign": r["campaign"]}
            # 0 인 지표는 저장 생략 (DB 무료 한도 절약 — 집계 시 없는 지표 = 0)
            out += [fact(d, "naver_keyword", k, r[k], **dims) for k in METRICS if k == "impressions" or r[k]]
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
