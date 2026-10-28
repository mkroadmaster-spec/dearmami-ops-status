"""경쟁사 수집기 — 네이버 데이터랩 검색 트렌드(상대지수)."""
from __future__ import annotations

from .. import config
from ..clients.naver_datalab import NaverDataLab
from .base import Fact, fact


def collect(store, d: str) -> list[Fact]:
    brands = config.competitor_names()
    if not brands:
        return []
    out: list[Fact] = []
    for grp in NaverDataLab().trend(brands, d, d):
        for row in grp.get("data", []):
            if row.get("period") == d:
                out.append(fact(d, "competitor", "trend_ratio", float(row.get("ratio", 0)), brand=grp.get("title", "")))
    return out
