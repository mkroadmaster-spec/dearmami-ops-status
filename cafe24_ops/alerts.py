"""오늘의 브리핑 (keek 형식) — 이모지 요약 줄 + 한 문장 + 4박스(핵심지표·7일 평균 급등락·이상치/신규 등장·광고 지표).

digest(store, d) → {date, headline, summary, lines[], core[], avg7[], anomalies[], ads[], failures[]}"""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Any

from .etl import breakdown
from .etl.aggregate import compare, derive, sum_range


def _won(v: float | None) -> str:
    return "—" if v is None else f"₩{v:,.0f}"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:+.0f}%"


def _x(v: float | None) -> str:
    return "—" if v is None else f"{v/100:.2f}x"


def _day(store, d: str) -> dict[str, float | None]:
    k = store.kpi_range(d, d).get(d, {})
    return derive(k) if k else {}


def digest(store, d: str) -> dict[str, Any]:
    base = _date.fromisoformat(d)
    cur = _day(store, d)
    empty = {"date": d, "headline": "데이터 없음", "summary": "해당 날짜의 수집 데이터가 없습니다.", "lines": [], "core": [],
             "avg7": [], "anomalies": [], "ads": [], "failures": [], "empty": True}
    if not cur:
        return empty
    d1 = _day(store, (base - timedelta(days=1)).isoformat())
    d7 = _day(store, (base - timedelta(days=7)).isoformat())
    d365 = _day(store, (base - timedelta(days=365)).isoformat())
    wk = store.kpi_range((base - timedelta(days=7)).isoformat(), (base - timedelta(days=1)).isoformat())
    avg7: dict[str, float | None] = {}
    if wk:
        s = sum_range(wk)
        n = s.get("days") or 1
        for m in ("gross_sales", "orders", "aov", "visitors", "conversion_rate", "ad_cost", "roas"):
            v = s.get(m)
            if v is None:
                continue
            avg7[m] = float(v) / n if m in ("gross_sales", "orders", "visitors", "ad_cost") else float(v)
    c1, c7, c365, cavg = compare(cur, d1), compare(cur, d7), compare(cur, d365), compare(cur, avg7)

    def tri(m: str) -> str:
        return f"전일 {_pct(c1[m]['pct'])} · 전주 {_pct(c7[m]['pct'])} · 전년 {_pct(c365[m]['pct'])}"

    gs, orders, aov = cur.get("gross_sales"), cur.get("orders") or 0, cur.get("aov")
    vis, cr = cur.get("visitors"), cur.get("conversion_rate")
    gs_avg = cavg.get("gross_sales", {}).get("pct")

    # ---- 이모지 요약 줄 ----
    lines = [f"💰 매출 {_won(gs)} · 주문 {orders:,.0f}건 · 객단가 {_won(aov)}" + (f" ({gs_avg:+.0f}% vs 7일평균)" if gs_avg is not None else "")
             + (f"   👀 방문자 {vis:,.0f} · 전환율 {cr or 0:.2f}%" if vis is not None else "   👀 방문자 — (GA4 미연결)")
             + (f"   📱 모바일 {cur.get('mobile_share') or 0:.0f}% · PC {100 - (cur.get('mobile_share') or 0):.0f}%" if cur.get("mobile_share") is not None else "")
             + (f"   👥 신규 {cur.get('new_order_share') or 0:.0f}% · 재구매 {100 - (cur.get('new_order_share') or 0):.0f}%" if cur.get("new_order_share") is not None else "")]
    cats = breakdown.category_sales(store, d, d, top=2)
    best = breakdown.best_products(store, d, d, top=3)
    if cats:
        lines.append("🏷 카테고리 " + ", ".join(f"{c['category']} {_won(c['sales'])}" for c in cats)
                     + ("   🏆 베스트 " + ", ".join(b["product"] for b in best) if best else ""))
    if cur.get("ad_cost") is not None:
        lines.append(f"📣 광고비 {_won(cur['ad_cost'])} · ROAS {_x(cur.get('roas'))} · 매출대비 {cur.get('ad_cost_ratio') or 0:.2f}%"
                     + (f"   ⛔ 품절 {cur['soldout_products']:,.0f}개" if cur.get("soldout_products") else ""))

    # ---- 한 문장 ----
    parts = [f"매출 {_won(gs)}" + (f", 7일 평균 대비 {gs_avg:+.0f}%로 {'호조' if gs_avg >= 10 else '부진' if gs_avg <= -10 else '평이'}" if gs_avg is not None else "")]
    if cr is not None:
        cp = cavg.get("conversion_rate", {}).get("pct")
        parts.append(f"전환율 {cr:.2f}%" + (f"({cp:+.0f}%)" if cp is not None else ""))
    if cur.get("roas") is not None:
        parts.append(f"광고 ROAS {_x(cur['roas'])}")
    summary = " · ".join(parts)

    # ---- 4박스 ----
    core = [f"매출 {_won(gs)} — {tri('gross_sales')}", f"주문건수 {orders:,.0f} — {tri('orders')}", f"객단가 {_won(aov)} — {tri('aov')}"]
    if cr is not None:
        core += [f"구매전환율 {cr:.2f}% — {tri('conversion_rate')}", f"방문자 {vis:,.0f} — {tri('visitors')}"]
    avg_lines = []
    label = {"conversion_rate": "구매전환율", "aov": "객단가", "visitors": "방문자", "orders": "주문건수", "gross_sales": "매출", "ad_cost": "광고비", "roas": "ROAS"}
    for m, ch in sorted(((m, cavg[m]["pct"]) for m in avg7 if cavg.get(m, {}).get("pct") is not None), key=lambda x: -abs(x[1])):
        if abs(ch) >= 15:
            avg_lines.append(f"{label[m]} 7일 평균 대비 {ch:+.0f}% {'상승' if ch > 0 else '하락'}")
    anomalies = []
    if gs_avg is not None and abs(gs_avg) >= 30:
        anomalies.append(f"매출 7일 평균 대비 {gs_avg:+.0f}% — 원인(광고·품절·프로모션) 확인")
    low = [r for r in breakdown.cart_funnel(store, (base - timedelta(days=6)).isoformat(), d, 50)["rows"] if r["cannot_add"]][:3]
    if low:
        anomalies.append("담기 0건 상품(담을 수 없는 상태?): " + ", ".join(r["product"] for r in low))
    if cur.get("roas") is not None and cur["roas"] < 200:
        anomalies.append(f"광고 ROAS {_x(cur['roas'])} — 2.0x 미만, 채널별 성과 확인")
    kw_new = _new_keywords(store, d)
    if kw_new:
        anomalies.append("새로 유입된 검색어: " + ", ".join(kw_new[:3]))
    ads = []
    if cur.get("ad_cost") is not None:
        def two(m: str) -> str:
            return f"전일 {_pct(c1[m]['pct'])} · 전주 {_pct(c7[m]['pct'])}"
        ads = [f"광고비 {_won(cur['ad_cost'])} — {two('ad_cost')}", f"광고매출 {_won(cur.get('ad_revenue'))} — {two('ad_revenue')}",
               f"ROAS {_x(cur.get('roas'))} — {two('roas')}", f"CTR {cur.get('ctr') or 0:.2f}% — {two('ctr')}",
               f"CPC ₩{cur.get('cpc') or 0:,.0f} — {two('cpc')}", f"매출대비 {cur.get('ad_cost_ratio') or 0:.2f}% — {two('ad_cost_ratio')}"]

    failures = sorted({r["source"] for r in store.recent_logs(300) if r["date"] == d and r["status"] in ("fail", "partial")})
    if failures:
        anomalies.append("🔴 수집 실패/부분 실패 채널: " + ", ".join(failures))
    headline = "특이사항 없음" if not anomalies else "확인 필요 항목 있음"
    return {"date": d, "headline": headline, "summary": summary, "lines": lines, "core": core, "avg7": avg_lines,
            "anomalies": anomalies, "ads": ads, "failures": failures, "empty": False}


def _new_keywords(store, d: str) -> list[str]:
    base = _date.fromisoformat(d)
    cur = {r["keyword"] for r in breakdown.keywords(store, d, d, top=30)}
    prev = {r["keyword"] for r in breakdown.keywords(store, (base - timedelta(days=14)).isoformat(), (base - timedelta(days=1)).isoformat(), top=200)}
    return sorted(cur - prev)
