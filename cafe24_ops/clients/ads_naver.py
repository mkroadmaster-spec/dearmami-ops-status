"""네이버 검색광고(SA) API — 캠페인/광고그룹/키워드 → /stats 집계. 파워링크(WEB_SITE)/플레이스(PLACE) 자동 분리.

필요: NAVER_SA_API_KEY, NAVER_SA_SECRET_KEY, NAVER_SA_CUSTOMER_ID (3개 모두 콘솔에서 바로 복사 — 가장 쉬움)
함정: /stats 의 ids 는 동일 엔티티 유형만 (캠페인 cmp- / 광고그룹 grp- / 키워드 nkw- 혼합 금지).
키워드 메타(캠페인→광고그룹→키워드)는 날짜 무관 → 프로세스 캐시(백필 시 매일 재크롤 방지).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from functools import lru_cache
from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("NAVER_SA_API_KEY", "NAVER_SA_SECRET_KEY", "NAVER_SA_CUSTOMER_ID")
HOST = "https://api.searchad.naver.com"
STAT_FIELDS = ["impCnt", "clkCnt", "salesAmt", "ccnt", "convAmt"]


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


def _agg(rows: list[dict[str, Any]]) -> dict[str, float]:
    a = {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0}
    for r in rows:
        a["ad_cost"] += float(r.get("salesAmt", 0)); a["impressions"] += float(r.get("impCnt", 0))
        a["clicks"] += float(r.get("clkCnt", 0)); a["conversions"] += float(r.get("ccnt", 0))
        a["ad_revenue"] += float(r.get("convAmt", 0))
    return a


class NaverSAClient:
    def __init__(self):
        self.api_key = config.env("NAVER_SA_API_KEY")
        self.secret = config.env("NAVER_SA_SECRET_KEY")
        self.customer_id = config.env("NAVER_SA_CUSTOMER_ID")

    def _headers(self, method: str, uri: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(self.secret.encode(), f"{ts}.{method}.{uri}".encode(), hashlib.sha256).digest()).decode()
        return {"X-Timestamp": ts, "X-API-KEY": self.api_key, "X-Customer": self.customer_id,
                "X-Signature": sig, "Content-Type": "application/json"}

    def get(self, uri: str, params: dict[str, Any] | None = None) -> Any:
        r = requests.get(HOST + uri, headers=self._headers("GET", uri), params=params, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"NaverSA GET {uri} {r.status_code}: {r.text[:300]}")
        return r.json()

    # ---- 메타 (캐시) ----
    @lru_cache(maxsize=1)
    def campaigns(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.get("/ncc/campaigns"))

    @lru_cache(maxsize=1)
    def adgroups(self) -> tuple[dict[str, Any], ...]:
        out: list[dict[str, Any]] = []
        for c in self.campaigns():
            out += self.get("/ncc/adgroups", {"nccCampaignId": c["nccCampaignId"]})
        return tuple(out)

    @lru_cache(maxsize=1)
    def keywords(self) -> tuple[dict[str, Any], ...]:
        out: list[dict[str, Any]] = []
        for g in self.adgroups():
            if g.get("adgroupType", "WEB_SITE") == "WEB_SITE":
                out += self.get("/ncc/keywords", {"nccAdgroupId": g["nccAdgroupId"]})
        return tuple(out)

    # ---- stats (유형별 분리 호출, 100개 청크) ----
    def stats(self, ids: list[str], d: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i in range(0, len(ids), 100):
            data = self.get("/stats", {"ids": ",".join(ids[i:i + 100]), "fields": json.dumps(STAT_FIELDS),
                                       "timeRange": json.dumps({"since": d, "until": d})})
            out.extend(data.get("data", []))
        return out

    def daily_by_type(self, d: str) -> dict[str, dict[str, float]]:
        """{'naver_powerlink': {...}, 'naver_place': {...}} — 캠페인 campaignTp 로 분리."""
        type_of = {c["nccCampaignId"]: c.get("campaignTp", "") for c in self.campaigns()}
        groups: dict[str, list] = {"naver_powerlink": [], "naver_place": []}
        for row in self.stats(list(type_of), d):
            groups["naver_place" if type_of.get(row.get("id")) == "PLACE" else "naver_powerlink"].append(row)
        return {k: _agg(v) for k, v in groups.items() if v}

    def keyword_stats(self, d: str) -> list[dict[str, Any]]:
        """키워드 단위 (광고 히스토리 → 네이버 검색)."""
        camp = {c["nccCampaignId"]: c.get("name", "") for c in self.campaigns()}
        grp = {g["nccAdgroupId"]: g for g in self.adgroups()}
        kw = {k["nccKeywordId"]: k for k in self.keywords()}
        out = []
        for row in self.stats(list(kw), d):
            k = kw.get(row.get("id"), {})
            g = grp.get(k.get("nccAdgroupId"), {})
            out.append({"keyword_id": row.get("id"), "keyword": k.get("keyword", ""), "adgroup": g.get("name", ""),
                        "campaign": camp.get(g.get("nccCampaignId"), ""), **_agg([row])})
        return out

    def place_adgroup_stats(self, d: str) -> list[dict[str, Any]]:
        """플레이스 광고그룹 단위."""
        camp = {c["nccCampaignId"]: c for c in self.campaigns()}
        grps = [g for g in self.adgroups() if camp.get(g.get("nccCampaignId"), {}).get("campaignTp") == "PLACE"]
        by = {g["nccAdgroupId"]: g for g in grps}
        return [{"adgroup_id": r.get("id"), "adgroup": by.get(r.get("id"), {}).get("name", ""),
                 "campaign": camp.get(by.get(r.get("id"), {}).get("nccCampaignId"), {}).get("name", ""), **_agg([r])}
                for r in self.stats(list(by), d)]
