"""구글 애즈 소재(광고·실적최대화 애셋그룹) 수집기 — 광고 히스토리 '구글 소재'. source='google_creative'.

일자별로 API 를 부르면 장기 백필에서 호출 한도(탐색자 등급 하루 2,880회)를 넘기 쉬워
처음 요청된 날부터 30일 구간을 한 번에 받아 캐시한다(파이프라인은 날짜 오름차순). 대표 이미지는 실행당 1회 조회."""
from __future__ import annotations

from datetime import date as _date, timedelta

from ..clients import ads_google
from .base import Fact, fact

SRC = "google_creative"
METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")
WINDOW = 30
_cache: dict[str, list[dict]] = {}
_thumbs: dict[str, str] | None = None


def is_configured() -> bool:
    return ads_google.is_configured()


def _load(g: "ads_google.GoogleAdsClient", d: str) -> None:
    from ..pipeline import yesterday
    end = min(_date.fromisoformat(d) + timedelta(days=WINDOW - 1), _date.fromisoformat(yesterday()))
    end = max(end, _date.fromisoformat(d))
    rows = g.creative_rows(d, end.isoformat())
    day = _date.fromisoformat(d)
    while day <= end:
        _cache[day.isoformat()] = []
        day += timedelta(days=1)
    for r in rows:
        _cache.setdefault(r["date"], []).append(r)


def collect(store, d: str) -> list[Fact]:
    global _thumbs
    g = ads_google.GoogleAdsClient(store)
    if d not in _cache:
        _load(g, d)
    if _thumbs is None:
        try:
            _thumbs = g.creative_thumbnails()
        except Exception:  # noqa: BLE001  — 이미지는 보조 정보: 실패해도 성과는 저장
            _thumbs = {}
    out: list[Fact] = []
    for r in _cache.pop(d, []):
        dims = {"ad_id": r["ad_id"], "ad_name": r["ad_name"], "campaign": r["campaign"], "adset": r["adset"],
                "ad_type": r["ad_type"], "thumbnail_url": _thumbs.get(r["ad_id"], "")}
        out += [fact(d, SRC, k, r[k], **dims) for k in METRICS]
    return out
