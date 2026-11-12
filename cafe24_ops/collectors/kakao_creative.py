"""카카오모먼트 소재 수집기 — 광고 히스토리 '카카오 소재'. source='kakao_creative'.

리포트 API 는 5초당 1회라 일자별로 부르면 백필이 너무 길다 → 처음 요청된 날부터 31일 구간을 한 번에:
  ① campaigns/report 로 그 구간에 집행된 캠페인만 추린다
  ② 해당 캠페인의 광고그룹·소재 목록 (실행 중 캐시)
  ③ creatives/report (소재 100개씩) → 일자·소재별 성과
소재 이름·이미지(상세 API)는 DB(app_kv 'kakao_creative_meta')에 캐시해 매일 다시 부르지 않는다."""
from __future__ import annotations

import json
from datetime import date as _date, timedelta

from ..clients import ads_kakao
from .base import Fact, fact

SRC = "kakao_creative"
METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")
WINDOW = 31
KV_META = "kakao_creative_meta"
_cache: dict[str, list[dict]] = {}
_camps: list[dict] | None = None
_tree: dict[int, list[dict]] = {}   # campaign_id → [{id, name, adgroup}]


def is_configured() -> bool:
    return ads_kakao.is_configured()


def _creatives_of(k: "ads_kakao.KakaoMomentClient", cid: int) -> list[dict]:
    if cid not in _tree:
        rows = []
        for g in k.ad_groups(cid):
            for c in k.creatives(g["id"]):
                rows.append({"id": c["id"], "name": c.get("name", ""), "adgroup": g.get("name", "")})
        _tree[cid] = rows
    return _tree[cid]


def _load(store, k: "ads_kakao.KakaoMomentClient", d: str) -> None:
    global _camps
    from ..pipeline import yesterday
    end = max(min(_date.fromisoformat(d) + timedelta(days=WINDOW - 1), _date.fromisoformat(yesterday())), _date.fromisoformat(d))
    s, e = d, end.isoformat()
    if _camps is None:
        _camps = k.campaigns()
    names = {c["id"]: c.get("name", "") for c in _camps}
    crow = k.report_rows("campaigns", list(names), s, e)
    if any((r.get("dimensions") or {}).get("campaign_id") for r in crow):
        active = {int(r["dimensions"]["campaign_id"]) for r in crow
                  if (r.get("dimensions") or {}).get("campaign_id") and float((r.get("metrics") or {}).get("imp", 0) or 0) > 0}
    elif crow:  # 행은 있는데 캠페인 구분이 없으면 전체 캠페인을 대상으로 (느리지만 누락 없음)
        active = set(names)
    else:  # 그 구간 집행 없음
        active = set()
    info: dict[str, dict] = {}
    for cid in active:
        for c in _creatives_of(k, cid):
            info[str(c["id"])] = {"name": c["name"], "adgroup": c["adgroup"], "campaign": names.get(cid, "")}
    rows = k.report_rows("creatives", list(info), s, e) if info else []
    meta = json.loads(store.kv_get(KV_META) or "{}")
    day = _date.fromisoformat(s)
    while day <= end:
        _cache[day.isoformat()] = []
        day += timedelta(days=1)
    changed = False
    for r in rows:
        crid = str((r.get("dimensions") or {}).get("creative_id", ""))
        m = ads_kakao.metrics_of(r.get("metrics") or {})
        if not crid or m["impressions"] <= 0:
            continue
        if crid not in meta:  # 이미지·형식은 상세 API 로 1회만
            det = k.creative_detail(crid)
            meta[crid] = {"thumb": ads_kakao.creative_thumb(det), "format": det.get("format", "")}
            changed = True
        _cache.setdefault(r["start"], []).append({"ad_id": crid, **info.get(crid, {}), **meta[crid], **m})
    if changed:
        store.kv_set(KV_META, json.dumps(meta, ensure_ascii=False))


def collect(store, d: str) -> list[Fact]:
    k = ads_kakao.KakaoMomentClient(store)
    if d not in _cache:
        _load(store, k, d)
    out: list[Fact] = []
    for r in _cache.pop(d, []):
        dims = {"ad_id": r["ad_id"], "ad_name": r.get("name", ""), "campaign": r.get("campaign", ""), "adset": r.get("adgroup", ""),
                "ad_type": r.get("format", ""), "thumbnail_url": r.get("thumb", "")}
        out += [fact(d, SRC, x, r[x], **dims) for x in METRICS]
    return out
