"""facts → kpi_daily 집계 + 기간 합계/파생지표 재계산."""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Any

ADDITIVE = (
    "gross_sales", "orders", "new_orders", "returning_orders", "mobile_sales", "pc_sales",
    "mobile_orders", "pc_orders", "canceled_orders", "reviews",
    "visitors", "new_visitors", "returning_visitors", "sessions", "pageviews", "ga4_conversions",
    "cafe24_visits", "cafe24_first_visits", "cafe24_revisits",
    "ad_cost", "ad_revenue", "ad_clicks", "ad_impressions", "ad_conversions",
    "session_sec_total",
)


def _div(a: float | None, b: float | None, pct: bool = False) -> float | None:
    if a is None or not b:
        return None
    return a / b * (100 if pct else 1)


def derive(k: dict[str, float | None]) -> dict[str, float | None]:
    """합산 후 파생지표 재계산 (파생값은 절대 합산하지 않는다)."""
    k = dict(k)
    k["aov"] = _div(k.get("gross_sales"), k.get("orders"))
    k["conversion_rate"] = _div(k.get("orders"), k.get("visitors"), pct=True)
    k["roas"] = _div(k.get("ad_revenue"), k.get("ad_cost"), pct=True)
    k["ctr"] = _div(k.get("ad_clicks"), k.get("ad_impressions"), pct=True)
    k["cpc"] = _div(k.get("ad_cost"), k.get("ad_clicks"))
    k["mobile_share"] = _div(k.get("mobile_sales"), k.get("gross_sales"), pct=True)
    k["revisit_rate"] = _div(k.get("returning_visitors"), k.get("visitors"), pct=True)
    k["ad_cost_ratio"] = _div(k.get("ad_cost"), k.get("gross_sales"), pct=True)
    k["avg_session_sec"] = _div(k.get("session_sec_total"), k.get("sessions"))
    k["cpa"] = _div(k.get("ad_cost"), k.get("ad_conversions"))
    k["cvr"] = _div(k.get("ad_conversions"), k.get("ad_clicks"), pct=True)
    k["new_order_share"] = _div(k.get("new_orders"), k.get("orders"), pct=True)
    return k


def kpis_from_facts(facts: list[dict[str, Any]]) -> dict[str, float | None]:
    k: dict[str, float | None] = {}
    avg_sec: float | None = None
    have_ga4 = any(f["source"] == "ga4" and f["metric"] == "visitors" for f in facts)
    for f in facts:
        s, m, v = f["source"], f["metric"], float(f["value"] or 0)
        if s == "cafe24" and m != "product_sales":
            k[m] = (k.get(m) or 0) + v
        elif s == "ga4":
            if m == "avg_session_sec":
                avg_sec = v
                continue
            key = "ga4_conversions" if m == "conversions" else m
            k[key] = (k.get(key) or 0) + v
        elif s == "cafe24_analytics" and m in ("visit_count", "first_visit_count", "re_visit_count"):
            key = {"visit_count": "cafe24_visits", "first_visit_count": "cafe24_first_visits",
                   "re_visit_count": "cafe24_revisits"}[m]
            k[key] = (k.get(key) or 0) + v
        elif s == "ads":
            key = {"ad_cost": "ad_cost", "ad_revenue": "ad_revenue", "clicks": "ad_clicks",
                   "impressions": "ad_impressions", "conversions": "ad_conversions"}.get(m)
            if key:
                k[key] = (k.get(key) or 0) + v
    if avg_sec is not None and k.get("sessions"):
        k["session_sec_total"] = avg_sec * float(k["sessions"])  # 평균은 합산 불가 → 총합으로 보관
    # 방문자: GA4 우선, 없으면 카페24 통계 '방문' (정의가 달라 UI 에 출처 표기)
    if not have_ga4 and k.get("cafe24_visits") is not None:
        k["visitors"] = k["cafe24_visits"]
        k["visitors_source"] = 0  # 0 = cafe24_analytics, 1 = ga4
    elif have_ga4:
        k["visitors_source"] = 1
    return derive(k)


def aggregate_day(store, d: str) -> dict[str, float | None]:
    facts = store.facts(d, d)
    k = kpis_from_facts(facts)
    store.upsert_kpi(d, k)
    return k


def sum_range(kpi_by_date: dict[str, dict[str, float | None]]) -> dict[str, float | None]:
    tot: dict[str, float | None] = {}
    for day in kpi_by_date.values():
        for m in ADDITIVE:
            if day.get(m) is not None:
                tot[m] = (tot.get(m) or 0) + float(day[m])
    tot["days"] = len(kpi_by_date)
    return derive(tot)


def previous_range(date_from: str, date_to: str) -> tuple[str, str]:
    a, b = _date.fromisoformat(date_from), _date.fromisoformat(date_to)
    n = (b - a).days + 1
    return (a - timedelta(days=n)).isoformat(), (a - timedelta(days=1)).isoformat()


def compare(cur: dict[str, float | None], prev: dict[str, float | None]) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    keys = set(cur) | set(prev)
    for m in keys:
        c, p = cur.get(m), prev.get(m)
        delta = None if c is None or p is None else c - p
        pct = None if delta is None or not p else delta / p * 100
        out[m] = {"cur": c, "prev": p, "delta": delta, "pct": pct}
    return out
