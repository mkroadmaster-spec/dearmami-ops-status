"""Meta 소재(광고 레벨) 수집기 — 광고 히스토리 탭. source='creative'."""
from __future__ import annotations

from ..clients import ads_meta
from .base import Fact, fact

METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue", "reach", "frequency")


def is_configured() -> bool:
    return ads_meta.is_configured()


def collect(store, d: str) -> list[Fact]:
    m = ads_meta.MetaAdsClient(store)
    rows = [r for r in m.ad_insights(d) if r["impressions"] > 0]
    thumbs = m.creatives([r["ad_id"] for r in rows])
    out: list[Fact] = []
    for r in rows:
        t = thumbs.get(r["ad_id"], {})
        dims = {"ad_id": r["ad_id"], "ad_name": r["ad_name"], "campaign": r["campaign"], "adset": r["adset"],
                "thumbnail_url": t.get("image_url") or t.get("thumbnail_url", "")}
        out += [fact(d, "creative", k, r.get(k, 0), **dims) for k in METRICS]
    return out
