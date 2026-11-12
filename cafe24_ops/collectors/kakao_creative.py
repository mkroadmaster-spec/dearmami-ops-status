"""카카오모먼트 소재 수집기 — 광고 히스토리 '카카오 소재'. source='kakao_creative'.

리포트 API 는 5초당 1회 + 잦은 429 라 일자별로 부르면 백필이 너무 길다 → 처음 요청된 날부터 31일 구간을 한 번에:
  ① 광고그룹 집행기간(schedule)으로 그 구간에 돌았을 수 있는 광고그룹만 추린다 (리포트 호출 없음, app_kv 캐시)
  ② 그 캠페인들만 campaigns/report → 실제 노출 있던 캠페인
  ③ 해당 광고그룹의 소재 목록 → creatives/report → 일자·소재별 성과 (하루 비용 상위 TOP 개만 저장)
소재 이름·이미지(상세 API)는 DB(app_kv 'kakao_creative_meta')에 캐시해 매일 다시 부르지 않는다."""
from __future__ import annotations

import json
from datetime import date as _date, timedelta

from ..clients import ads_kakao
from .base import Fact, fact

SRC = "kakao_creative"
METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")
WINDOW = 31
TOP = 40  # 하루 소재 상한 (DB 무료 한도)
KV_META = "kakao_creative_meta"
KV_SCHED = "kakao_adgroup_sched"
_cache: dict[str, list[dict]] = {}
_camps: list[dict] | None = None
_groups: dict[str, dict] | None = None  # adgroup_id → {campaign, name, begin, end}
_crs: dict[str, list[dict]] = {}        # adgroup_id → [{id, name}]


def is_configured() -> bool:
    return ads_kakao.is_configured()


def _ad_groups(store, k: "ads_kakao.KakaoMomentClient", today: str) -> dict[str, dict]:
    """전체 광고그룹 + 집행기간. 이미 끝난 광고그룹은 DB 캐시를 그대로 쓰고 나머지만 상세 조회."""
    global _groups
    if _groups is not None:
        return _groups
    cached = json.loads(store.kv_get(KV_SCHED) or "{}")
    out: dict[str, dict] = {}
    for c in _camps or []:
        for g in k.ad_groups(c["id"]):
            gid = str(g["id"])
            old = cached.get(gid)
            if old and old.get("end") and old["end"] < today:
                out[gid] = old
                continue
            sch = (k.ad_group_detail(gid).get("schedule") or {})
            out[gid] = {"campaign": c["id"], "name": g.get("name", ""), "begin": sch.get("beginDate") or "", "end": sch.get("endDate") or ""}
    store.kv_set(KV_SCHED, json.dumps(out, ensure_ascii=False))
    _groups = out
    return out


def _log(t0: float, msg: str) -> None:
    import time
    print(f"[kakao_creative] {time.time() - t0:5.0f}s {msg}", flush=True)


def _load(store, k: "ads_kakao.KakaoMomentClient", d: str) -> None:
    global _camps
    import time
    t0 = time.time()
    from ..pipeline import yesterday
    end = max(min(_date.fromisoformat(d) + timedelta(days=WINDOW - 1), _date.fromisoformat(yesterday())), _date.fromisoformat(d))
    s, e = d, end.isoformat()
    if _camps is None:
        _camps = k.campaigns()
    names = {c["id"]: c.get("name", "") for c in _camps}
    groups = _ad_groups(store, k, yesterday())
    _log(t0, f"광고그룹 {len(groups)}개 집행기간 확인")
    # 집행기간이 구간과 겹치는 광고그룹 (기간 정보 없으면 포함)
    cand = {gid: g for gid, g in groups.items() if (not g["begin"] or g["begin"] <= e) and (not g["end"] or g["end"] >= s)}
    cand_camps = sorted({g["campaign"] for g in cand.values()})
    _log(t0, f"{s}~{e} 후보 광고그룹 {len(cand)}개 · 캠페인 {len(cand_camps)}개")
    crow = k.report_rows("campaigns", cand_camps, s, e) if cand_camps else []
    if any((r.get("dimensions") or {}).get("campaign_id") for r in crow):
        active = {int(r["dimensions"]["campaign_id"]) for r in crow
                  if (r.get("dimensions") or {}).get("campaign_id") and float((r.get("metrics") or {}).get("imp", 0) or 0) > 0}
    else:
        active = set(cand_camps) if crow else set()
    _log(t0, f"캠페인 리포트 {len(crow)}행 → 집행 캠페인 {len(active)}개")
    info: dict[str, dict] = {}
    for gid, g in cand.items():
        if g["campaign"] not in active:
            continue
        if gid not in _crs:
            _crs[gid] = [{"id": c["id"], "name": c.get("name", "")} for c in k.creatives(int(gid))]
        for c in _crs[gid]:
            info[str(c["id"])] = {"name": c["name"], "adgroup": g["name"], "campaign": names.get(g["campaign"], "")}
    _log(t0, f"소재 {len(info)}개 목록")
    rows = k.report_rows("creatives", list(info), s, e) if info else []
    _log(t0, f"소재 리포트 {len(rows)}행")
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
    rows = sorted(_cache.pop(d, []), key=lambda r: (-r["ad_cost"], -r["clicks"], -r["impressions"]))[:TOP]
    for r in rows:
        dims = {"ad_id": r["ad_id"], "ad_name": r.get("name", ""), "campaign": r.get("campaign", ""), "adset": r.get("adgroup", ""),
                "ad_type": r.get("format", ""), "thumbnail_url": r.get("thumb", "")}
        out += [fact(d, SRC, x, r[x], **dims) for x in METRICS if x == "impressions" or r[x]]  # 0 지표 생략
    return out
