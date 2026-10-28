"""주간/월간 리포트 — 기간 무관 코어 `period_report_data` + 주/월 경계 래퍼.

주간: 지난주(월~일) vs 전주. `latest_complete_week` 는 데이터가 있는 완결 주로 폴백 → 탭이 지난주가 아닌 주를 보여주면 수집 구멍 신호.
월간: 전월 vs 전전월. 문구는 `prev_word`(전주/전월)로만 — 하드코딩 금지.
리포트는 빈 채로도 렌더되므로 `missing_dates` 를 먼저 볼 것.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date as _date, timedelta
from typing import Any

from . import breakdown
from .aggregate import compare, sum_range

WEEK_MIN_VIEWS = 50
MONTH_MIN_VIEWS = 200
SUMMARY_KEYS = ("gross_sales", "orders", "aov", "visitors", "conversion_rate", "ad_cost", "roas", "ad_cost_ratio",
                "new_orders", "returning_orders", "sessions", "ga4_conversions")


def _dates(f: str, t: str) -> list[str]:
    a, b = _date.fromisoformat(f), _date.fromisoformat(t)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def period_report_data(store, f: str, t: str, pf: str, pt: str, prev_word: str, min_views: int) -> dict[str, Any]:
    kpi_cur, kpi_prev = store.kpi_range(f, t), store.kpi_range(pf, pt)
    cur, prev = sum_range(kpi_cur), sum_range(kpi_prev)
    cmp = compare(cur, prev)
    missing = [d for d in _dates(f, t) if d not in kpi_cur]

    # 매체별
    ch_cur = breakdown.ads_by_channel(store, f, t)
    ch_prev = {r["channel"]: r for r in breakdown.ads_by_channel(store, pf, pt)}
    channels = []
    for r in ch_cur:
        p = ch_prev.get(r["channel"], {})
        channels.append({**r, "prev_ad_cost": p.get("ad_cost"), "prev_roas": p.get("roas"), "prev_ad_conversions": p.get("ad_conversions"),
                         "ad_cost_pct": ((r["ad_cost"] - p["ad_cost"]) / p["ad_cost"] * 100) if p.get("ad_cost") else None})

    # 구매 퍼널 병목: 조회→담기→주문 단계별 전환율을 비교기간과 대조, 더 크게 떨어진 단계 = 병목
    fun, pfun = breakdown.cart_funnel(store, f, t, min_views), breakdown.cart_funnel(store, pf, pt, min_views)
    tc, tp = fun["totals"], pfun["totals"]
    stages = [{"stage": "조회→담기", "rate": tc["cart_rate"], "prev_rate": tp["cart_rate"]},
              {"stage": "담기→주문", "rate": tc["order_rate"], "prev_rate": tp["order_rate"]}]
    for s in stages:
        s["delta_pt"] = (s["rate"] - s["prev_rate"]) if (s["rate"] is not None and s["prev_rate"] is not None) else None
    worst = min((s for s in stages if s["delta_pt"] is not None), key=lambda s: s["delta_pt"], default=None)
    funnel = {"totals": tc, "prev_totals": tp, "stages": stages,
              "bottleneck": worst["stage"] if worst and worst["delta_pt"] < 0 else None,
              "low_cart_products": [r for r in fun["rows"] if r["bottleneck"] or r["cannot_add"]][:8], "min_views": min_views}

    # 베스트 (순위 변동)
    best_prev = {r["product_no"]: r["rank"] for r in breakdown.best_products(store, pf, pt, top=50)}
    best = [{**r, "prev_rank": best_prev.get(r["product_no"])} for r in breakdown.best_products(store, f, t, top=10)]

    # 고객 구성
    members = breakdown.shop_analytics(store, f, t)["members"] if kpi_cur else []
    customers = {"new_orders": cur.get("new_orders"), "returning_orders": cur.get("returning_orders"),
                 "prev_new_orders": prev.get("new_orders"), "prev_returning_orders": prev.get("returning_orders"),
                 "mobile_share": cur.get("mobile_share"), "prev_mobile_share": prev.get("mobile_share"),
                 "members": members}

    # 검색어 (순위 변동)
    kw_prev = {r["keyword"]: i + 1 for i, r in enumerate(breakdown.keywords(store, pf, pt, top=50))}
    kws = [{**r, "rank": i + 1, "prev_rank": kw_prev.get(r["keyword"])} for i, r in enumerate(breakdown.keywords(store, f, t, top=10))]

    # 한줄 요약
    gs = cmp.get("gross_sales", {})
    head = f"매출 {_won(cur.get('gross_sales'))} ({prev_word} 대비 {_pct(gs.get('pct'))}) · 주문 {cur.get('orders') or 0:,.0f}건 · " \
           f"객단가 {_won(cur.get('aov'))} · 광고비 {_won(cur.get('ad_cost'))} · ROAS {cur.get('roas') or 0:,.0f}%"
    good = [k for k in ("gross_sales", "orders", "conversion_rate", "roas", "visitors") if (cmp.get(k, {}).get("pct") or 0) >= 5]
    bad = [k for k in ("gross_sales", "orders", "conversion_rate", "roas", "visitors") if (cmp.get(k, {}).get("pct") or 0) <= -5]
    return {
        "range": {"from": f, "to": t}, "prev_range": {"from": pf, "to": pt}, "prev_word": prev_word,
        "headline": head, "missing_dates": missing, "empty": not kpi_cur,
        "summary": {k: {"cur": cur.get(k), "prev": prev.get(k), "pct": cmp.get(k, {}).get("pct")} for k in SUMMARY_KEYS},
        "better": good, "worse": bad,
        "channels": channels, "funnel": funnel, "best": best, "customers": customers, "keywords": kws,
        "ga4_channels": breakdown.ga4_channels(store, f, t, top=8),
        "categories": breakdown.category_sales(store, f, t, top=6),
    }


def _won(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1_0000_0000:
        return f"{v/1_0000_0000:.1f}억원"
    if abs(v) >= 1_0000:
        return f"{v/1_0000:,.0f}만원"
    return f"{v:,.0f}원"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:+.1f}%"


# ---------------- 주간 ----------------
def week_bounds(any_day: str) -> tuple[str, str]:
    d = _date.fromisoformat(any_day)
    mon = d - timedelta(days=d.weekday())
    return mon.isoformat(), (mon + timedelta(days=6)).isoformat()


def latest_complete_week(store, today: str | None = None) -> tuple[str, str]:
    """오늘 기준 지난주(월~일). 그 주에 데이터가 하나도 없으면 데이터가 있는 가장 최근 완결 주로 폴백."""
    _, mx = store.date_bounds()
    today_d = _date.fromisoformat(today) if today else _date.today()
    last_sun = today_d - timedelta(days=today_d.weekday() + 1)
    f, t = week_bounds(last_sun.isoformat())
    for _ in range(8):
        if store.kpi_range(f, t):
            return f, t
        f, t = week_bounds((_date.fromisoformat(f) - timedelta(days=1)).isoformat())
    return f, t


def weekly_report(store, week: str | None = None, today: str | None = None) -> dict[str, Any]:
    f, t = week_bounds(week) if week else latest_complete_week(store, today)
    pf, pt = week_bounds((_date.fromisoformat(f) - timedelta(days=1)).isoformat())
    data = period_report_data(store, f, t, pf, pt, "전주", WEEK_MIN_VIEWS)
    data["kind"] = "weekly"
    data["title"] = f"주간 리포트 {f} ~ {t}"
    return data


# ---------------- 월간 ----------------
def month_bounds(ym: str) -> tuple[str, str]:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{monthrange(y, m)[1]:02d}"


def latest_complete_month(today: str | None = None) -> str:
    d = _date.fromisoformat(today) if today else _date.today()
    first = d.replace(day=1) - timedelta(days=1)
    return first.strftime("%Y-%m")


def monthly_report(store, month: str | None = None, today: str | None = None) -> dict[str, Any]:
    ym = month or latest_complete_month(today)
    f, t = month_bounds(ym)
    prev_ym = (_date.fromisoformat(f) - timedelta(days=1)).strftime("%Y-%m")
    pf, pt = month_bounds(prev_ym)
    data = period_report_data(store, f, t, pf, pt, "전월", MONTH_MIN_VIEWS)
    data["kind"] = "monthly"
    data["title"] = f"월간 리포트 {ym}"
    return data
