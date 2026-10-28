"""facts 직접 집계 — 채널별 광고, 카테고리/베스트, 접속통계 9블록, GA4 사이트분석, 소재/키워드/플레이스, 경쟁사, 기간비교."""
from __future__ import annotations

from collections import defaultdict
from datetime import date as _date, timedelta
from statistics import median
from typing import Any

from .aggregate import compare, derive

CHANNEL_LABEL = {"meta": "Meta", "naver_powerlink": "네이버 파워링크", "naver_place": "네이버 플레이스",
                 "google": "Google", "kakao": "카카오", "other": "기타/자연"}
_ADS_KEY = {"ad_cost": "ad_cost", "ad_revenue": "ad_revenue", "clicks": "ad_clicks",
            "impressions": "ad_impressions", "conversions": "ad_conversions"}


def _group(store, f: str, t: str, source: str, key_dims: tuple[str, ...], metric_map: dict[str, str] | None = None,
           metric: str | None = None) -> dict[tuple, dict[str, Any]]:
    """facts 를 dims 키로 묶어 합산. 반환 {key: {dims..., metric: sum}}"""
    out: dict[tuple, dict[str, Any]] = {}
    for x in store.facts(f, t, source=source, metric=metric):
        key = tuple(x["dims"].get(k, "") for k in key_dims)
        row = out.setdefault(key, {k: x["dims"].get(k, "") for k in key_dims} | {"_dims": x["dims"]})
        m = (metric_map or {}).get(x["metric"], x["metric"])
        row[m] = (row.get(m) or 0) + float(x["value"] or 0)
    return out


# ---------------- 기간 비교 (전일 / 전주 / 전년) ----------------
PERIOD_METRICS = ("gross_sales", "orders", "aov", "visitors", "conversion_rate", "new_orders", "returning_orders",
                  "ad_cost", "roas", "ad_cost_ratio", "mobile_share", "reviews")


def period_comparison(store, d: str) -> dict[str, Any]:
    base = _date.fromisoformat(d)

    def day(x: _date) -> dict[str, float | None]:
        k = store.kpi_range(x.isoformat(), x.isoformat()).get(x.isoformat(), {})
        return derive(k) if k else {}

    cur = day(base)
    out = {"date": d, "rows": []}
    refs = {"prev_day": base - timedelta(days=1), "prev_week": base - timedelta(days=7), "prev_year": base - timedelta(days=365)}
    cmp = {k: compare(cur, day(v)) for k, v in refs.items()}
    for m in PERIOD_METRICS:
        out["rows"].append({"metric": m, "cur": cur.get(m),
                            **{f"{k}": {"val": cmp[k][m]["prev"] if m in cmp[k] else None,
                                        "pct": cmp[k][m]["pct"] if m in cmp[k] else None} for k in refs}})
    out["ref_dates"] = {k: v.isoformat() for k, v in refs.items()}
    return out


# ---------------- 광고 ----------------
def ads_by_channel(store, f: str, t: str) -> list[dict[str, Any]]:
    g = _group(store, f, t, "ads", ("channel",), _ADS_KEY)
    ga4 = ga4_conversions_by_channel(store, f, t)
    rows = []
    for (ch,), m in g.items():
        k = derive({x: m.get(x) for x in _ADS_KEY.values()})
        rows.append({"channel": ch, "label": CHANNEL_LABEL.get(ch, ch), "ga4_conversions": ga4.get(ch),
                     **{x: k.get(x) for x in ("ad_cost", "ad_revenue", "ad_clicks", "ad_impressions", "ad_conversions",
                                              "roas", "ctr", "cpc", "cpa", "cvr")}})
    rows.sort(key=lambda r: -(r["ad_cost"] or 0))
    return rows


def ads_trend(store, f: str, t: str, metric: str = "ad_cost") -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for x in store.facts(f, t, source="ads", metric=metric):
        by_day[x["date"]][x["dims"].get("channel", "unknown")] += float(x["value"] or 0)
    return [{"date": d, **chs} for d, chs in sorted(by_day.items())]


# ---------------- 카페24 ----------------
def category_sales(store, f: str, t: str, top: int = 10) -> list[dict[str, Any]]:
    cats: dict[str, float] = defaultdict(float)
    for x in store.facts(f, t, source="cafe24", metric="product_sales"):
        cats[x["dims"].get("category") or "기타"] += float(x["value"] or 0)
    total = sum(cats.values()) or 1
    rows = [{"category": c, "sales": v, "share": v / total * 100} for c, v in cats.items()]
    rows.sort(key=lambda r: -r["sales"])
    return rows[:top]


def best_products(store, f: str, t: str, top: int = 10) -> list[dict[str, Any]]:
    g = _group(store, f, t, "cafe24", ("product_no", "product"), metric="product_sales")
    rows = [{"product_no": k[0], "product": k[1], "sales": v.get("product_sales", 0)} for k, v in g.items()]
    rows.sort(key=lambda r: -r["sales"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows[:top]


def cart_funnel(store, f: str, t: str, min_views: int = 50) -> dict[str, Any]:
    """상품별 조회→담기→주문. 담기율은 기간 합계(담기÷조회)로 재계산(일자별 비율 합산 금지).
    병목 판정은 중위값의 절반 미만. 담기 0 = '담을 수 없는 상태' 신호."""
    g = _group(store, f, t, "cafe24_analytics", ("product_no", "product"))
    rows = []
    for k, v in g.items():
        views = v.get("product_views", 0)
        if views < min_views:
            continue
        carts, orders = v.get("product_cart_adds", 0), v.get("product_orders", 0)
        rows.append({"product_no": k[0], "product": k[1], "views": views, "cart_adds": carts, "orders": orders,
                     "cart_rate": carts / views * 100 if views else None,
                     "order_rate": orders / carts * 100 if carts else None})
    rates = [r["cart_rate"] for r in rows if r["cart_rate"] is not None]
    med = median(rates) if rates else None
    for r in rows:
        r["bottleneck"] = bool(med is not None and r["cart_rate"] is not None and r["cart_rate"] < med / 2)
        r["cannot_add"] = r["cart_adds"] == 0
    rows.sort(key=lambda r: -r["views"])
    tot_v = sum(r["views"] for r in rows); tot_c = sum(r["cart_adds"] for r in rows); tot_o = sum(r["orders"] for r in rows)
    return {"median_cart_rate": med, "min_views": min_views, "rows": rows,
            "totals": {"views": tot_v, "cart_adds": tot_c, "orders": tot_o,
                       "cart_rate": tot_c / tot_v * 100 if tot_v else None, "order_rate": tot_o / tot_c * 100 if tot_c else None}}


def _top_dim(store, f: str, t: str, source: str, metric: str, dim: str, top: int, out_key: str) -> list[dict[str, Any]]:
    g = _group(store, f, t, source, (dim,), metric=metric)
    rows = [{dim: k[0], out_key: v.get(metric, 0)} for k, v in g.items() if k[0]]
    rows.sort(key=lambda r: -r[out_key])
    return rows[:top]


def keywords(store, f: str, t: str, top: int = 15) -> list[dict[str, Any]]:
    return _top_dim(store, f, t, "cafe24_analytics", "keyword_visits", "keyword", top, "visits")


def shop_analytics(store, f: str, t: str) -> dict[str, Any]:
    """접속통계 섹션 9블록 + 비교기간 자동 계산."""
    from .aggregate import previous_range
    pf, pt = previous_range(f, t)
    days = (_date.fromisoformat(t) - _date.fromisoformat(f)).days + 1
    min_views = 50 if days <= 7 else 200
    funnel = cart_funnel(store, f, t, min_views)
    prev_funnel = cart_funnel(store, pf, pt, min_views)
    members = _group(store, f, t, "cafe24_analytics", ("member_type",))
    member_rows = [{"member_type": k[0], "orders": v.get("member_orders", 0), "sales": v.get("member_sales", 0)}
                   for k, v in members.items() if k[0]]
    vis = _group(store, f, t, "cafe24_analytics", (), )
    v = next(iter(vis.values()), {}) if vis else {}
    pv = next(iter(_group(store, pf, pt, "cafe24_analytics", ()).values()), {}) if days else {}
    visitors = {"visit_count": v.get("visit_count"), "first_visit_count": v.get("first_visit_count"), "re_visit_count": v.get("re_visit_count"),
                "revisit_rate": (v.get("re_visit_count", 0) / v["visit_count"] * 100) if v.get("visit_count") else None,
                "prev_visit_count": pv.get("visit_count")}
    return {
        "range": {"from": f, "to": t}, "prev_range": {"from": pf, "to": pt},
        "visitors": visitors,
        "funnel": funnel, "prev_funnel_totals": prev_funnel["totals"],
        "low_cart_products": [r for r in funnel["rows"] if r["bottleneck"] or r["cannot_add"]][:10],
        "keywords": keywords(store, f, t), "domains": _top_dim(store, f, t, "cafe24_analytics", "domain_visits", "domain", 10, "visits"),
        "ad_paths": _top_dim(store, f, t, "cafe24_analytics", "adpath_visits", "ad_channel", 10, "visits"),
        "pages": _top_dim(store, f, t, "cafe24_analytics", "page_views", "path", 10, "views"),
        "members": member_rows,
        "product_sales": sorted([{"product_no": k[0], "product": k[1], "orders": v.get("product_orders", 0), "qty": v.get("product_qty", 0)}
                                 for k, v in _group(store, f, t, "cafe24_analytics", ("product_no", "product")).items() if v.get("product_orders")],
                                key=lambda r: -r["orders"])[:10],
    }


# ---------------- GA4 사이트 분석 ----------------
def ga4_site(store, f: str, t: str) -> dict[str, Any]:
    from .aggregate import previous_range, sum_range
    pf, pt = previous_range(f, t)
    cur, prev = sum_range(store.kpi_range(f, t)), sum_range(store.kpi_range(pf, pt))
    keys = ("visitors", "sessions", "pageviews", "avg_session_sec", "new_visitors", "returning_visitors", "ga4_conversions", "revisit_rate")
    c = compare({k: cur.get(k) for k in keys}, {k: prev.get(k) for k in keys})
    return {"range": {"from": f, "to": t}, "metrics": {k: {"cur": cur.get(k), "prev": prev.get(k), "pct": c[k]["pct"]} for k in keys},
            "available": cur.get("sessions") is not None}


def ga4_channels(store, f: str, t: str, top: int = 15) -> list[dict[str, Any]]:
    g = _group(store, f, t, "ga4_channel", ("source_medium", "channel"))
    rows = []
    for k, v in g.items():
        s, conv = v.get("sessions", 0), v.get("conversions", 0)
        rows.append({"source_medium": k[0], "channel": k[1], "label": CHANNEL_LABEL.get(k[1], k[1]), "sessions": s,
                     "users": v.get("users", 0), "conversions": conv, "cvr": conv / s * 100 if s else None})
    rows.sort(key=lambda r: -r["sessions"])
    return rows[:top]


def ga4_conversions_by_channel(store, f: str, t: str) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for x in store.facts(f, t, source="ga4_channel", metric="conversions"):
        out[x["dims"].get("channel", "other")] += float(x["value"] or 0)
    return dict(out)


def ga4_pages(store, f: str, t: str, top: int = 10) -> list[dict[str, Any]]:
    g = _group(store, f, t, "ga4_page", ("path",))
    rows = [{"path": k[0], "pageviews": v.get("pageviews", 0), "users": v.get("users", 0)} for k, v in g.items()]
    rows.sort(key=lambda r: -r["pageviews"])
    return rows[:top]


# ---------------- 광고 히스토리 ----------------
def _ad_derive(m: dict[str, Any]) -> dict[str, Any]:
    k = derive({"ad_cost": m.get("ad_cost", 0), "ad_revenue": m.get("ad_revenue", 0), "ad_clicks": m.get("clicks", 0),
                "ad_impressions": m.get("impressions", 0), "ad_conversions": m.get("conversions", 0)})
    return {x: k.get(x) for x in ("ad_cost", "ad_revenue", "ad_clicks", "ad_impressions", "ad_conversions", "roas", "ctr", "cpc", "cpa", "cvr")}


def creatives_overview(store, f: str, t: str) -> list[dict[str, Any]]:
    """Meta 소재별 성과 + 피로도(최근 7일 CTR vs 기간 초반 7일 CTR, 평균 빈도)."""
    g = _group(store, f, t, "creative", ("ad_id",))
    tf = _date.fromisoformat(t)
    recent_from = (tf - timedelta(days=6)).isoformat()
    early_to = (_date.fromisoformat(f) + timedelta(days=6)).isoformat()
    recent = _group(store, recent_from, t, "creative", ("ad_id",))
    early = _group(store, f, early_to, "creative", ("ad_id",))

    def ctr(x: dict[str, Any] | None) -> float | None:
        if not x or not x.get("impressions"):
            return None
        return x.get("clicks", 0) / x["impressions"] * 100

    rows = []
    for (ad_id,), m in g.items():
        d = m["_dims"]
        imp = m.get("impressions", 0)
        freq = (m.get("frequency", 0) * 1.0)  # 일자별 frequency 합 → 일수로 평균
        n_days = len({x["date"] for x in store.facts(f, t, source="creative", metric="frequency") if x["dims"].get("ad_id") == ad_id}) or 1
        avg_freq = freq / n_days
        c_r, c_e = ctr(recent.get((ad_id,))), ctr(early.get((ad_id,)))
        drop = ((c_e - c_r) / c_e * 100) if (c_r is not None and c_e) else None
        level = "높음" if (drop is not None and drop >= 25) or avg_freq >= 3.5 else ("주의" if (drop is not None and drop >= 10) or avg_freq >= 2.5 else "정상")
        rows.append({"ad_id": ad_id, "ad_name": d.get("ad_name", ""), "campaign": d.get("campaign", ""), "adset": d.get("adset", ""),
                     "thumbnail_url": d.get("thumbnail_url", ""), "reach": m.get("reach", 0), "frequency": avg_freq,
                     "ctr_recent": c_r, "ctr_early": c_e, "ctr_drop_pct": drop, "fatigue": level, **_ad_derive(m)})
    rows.sort(key=lambda r: -(r["ad_cost"] or 0))
    return rows


def creative_trend(store, f: str, t: str, top: int = 5) -> dict[str, Any]:
    ids = [r["ad_id"] for r in creatives_overview(store, f, t)[:top]]
    by: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    names: dict[str, str] = {}
    for x in store.facts(f, t, source="creative"):
        aid = x["dims"].get("ad_id")
        if aid in ids and x["metric"] in ("impressions", "clicks"):
            by[aid][x["date"]][x["metric"]] += float(x["value"] or 0)
            names[aid] = x["dims"].get("ad_name", aid)
    dates = sorted({d for a in by.values() for d in a})
    series = [{"ad_id": aid, "ad_name": names.get(aid, aid),
               "ctr": [(by[aid][d]["clicks"] / by[aid][d]["impressions"] * 100) if by[aid].get(d, {}).get("impressions") else None for d in dates]}
              for aid in ids]
    return {"dates": dates, "series": series}


def keyword_report(store, f: str, t: str, sort: str = "ad_cost", top: int = 50) -> list[dict[str, Any]]:
    g = _group(store, f, t, "naver_keyword", ("keyword_id",))
    rows = [{"keyword_id": k[0], "keyword": v["_dims"].get("keyword", ""), "adgroup": v["_dims"].get("adgroup", ""),
             "campaign": v["_dims"].get("campaign", ""), **_ad_derive(v)} for k, v in g.items()]
    rows.sort(key=lambda r: -(r.get(sort) or 0))
    return rows[:top]


def place_report(store, f: str, t: str) -> list[dict[str, Any]]:
    g = _group(store, f, t, "naver_place", ("adgroup_id",))
    rows = [{"adgroup_id": k[0], "adgroup": v["_dims"].get("adgroup", ""), "campaign": v["_dims"].get("campaign", ""), **_ad_derive(v)}
            for k, v in g.items()]
    rows.sort(key=lambda r: -(r["ad_cost"] or 0))
    return rows


# ---------------- 경쟁사 ----------------
def competitor_trend(store, f: str, t: str) -> dict[str, Any]:
    by_brand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for x in store.facts(f, t, source="competitor", metric="trend_ratio"):
        by_brand[x["dims"].get("brand", "")].append({"date": x["date"], "ratio": x["value"]})
    return {"brands": [{"brand": b, "points": sorted(p, key=lambda r: r["date"])} for b, p in by_brand.items()]}
