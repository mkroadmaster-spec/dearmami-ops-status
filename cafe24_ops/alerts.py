"""오늘의 브리핑 — 전일·전주·전년 비교, 7일 평균 대비 급등락, 수집 실패 채널."""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Any

from .etl.aggregate import compare, derive, sum_range


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


def _day(store, d: str) -> dict[str, float | None]:
    k = store.kpi_range(d, d).get(d, {})
    return derive(k) if k else {}


def digest(store, d: str) -> dict[str, Any]:
    base = _date.fromisoformat(d)
    cur = _day(store, d)
    if not cur:
        return {"date": d, "headline": "해당 날짜의 수집 데이터가 없습니다.", "lines": [], "failures": [], "empty": True}

    d1 = _day(store, (base - timedelta(days=1)).isoformat())
    d7 = _day(store, (base - timedelta(days=7)).isoformat())
    d365 = _day(store, (base - timedelta(days=365)).isoformat())
    wk = store.kpi_range((base - timedelta(days=7)).isoformat(), (base - timedelta(days=1)).isoformat())
    avg7 = sum_range(wk) if wk else {}
    if avg7:
        n = avg7.get("days") or 1
        for m in ("gross_sales", "orders", "visitors", "ad_cost"):
            if avg7.get(m) is not None:
                avg7[m] = float(avg7[m]) / n

    lines: list[str] = []
    c1, c7, c365 = compare(cur, d1), compare(cur, d7), compare(cur, d365)

    gs = cur.get("gross_sales")
    lines.append(f"매출 {_won(gs)} · 주문 {cur.get('orders') or 0:,.0f}건 · 객단가 {_won(cur.get('aov'))}"
                 f" (전일 {_pct(c1['gross_sales']['pct'])}, 전주 {_pct(c7['gross_sales']['pct'])}"
                 + (f", 전년 {_pct(c365['gross_sales']['pct'])}" if d365 else "") + ")")

    if avg7.get("gross_sales") and gs is not None:
        dev = (gs - avg7["gross_sales"]) / avg7["gross_sales"] * 100
        if abs(dev) >= 30:
            lines.append(f"⚠ 매출이 최근 7일 평균 대비 {dev:+.0f}% — {'급등' if dev > 0 else '급락'}. 원인(광고·품절·프로모션) 확인 필요")

    if cur.get("visitors") is not None:
        src = "GA4" if cur.get("visitors_source") == 1 else "카페24 통계"
        lines.append(f"방문자 {cur['visitors']:,.0f}명({src}) · 구매전환율 {cur.get('conversion_rate') or 0:.2f}%"
                     f" (전주 {_pct(c7['visitors']['pct'])})")
    else:
        lines.append("방문자/전환율 — GA4 미연결 (docs/GA4-SETUP.md)")

    if cur.get("ad_cost"):
        lines.append(f"광고비 {_won(cur['ad_cost'])} · ROAS {cur.get('roas') or 0:,.0f}% · 광고비율 {cur.get('ad_cost_ratio') or 0:.1f}%"
                     f" (전주 광고비 {_pct(c7['ad_cost']['pct'])})")
        if (cur.get("roas") or 0) < 200:
            lines.append("⚠ ROAS 200% 미만 — 채널별 성과 확인(광고 탭)")

    if cur.get("new_orders") is not None and cur.get("orders"):
        lines.append(f"신규 {cur['new_orders']:,.0f} / 재구매 {cur.get('returning_orders') or 0:,.0f} · "
                     f"모바일 비중 {cur.get('mobile_share') or 0:.0f}%")

    failures = [r for r in store.recent_logs(200) if r["date"] == d and r["status"] in ("fail", "partial")]
    fails = sorted({f"{r['source']}" for r in failures})
    if fails:
        lines.append("🔴 수집 실패/부분 실패 채널: " + ", ".join(fails))

    headline = "특이사항 없음" if not any(l.startswith(("⚠", "🔴")) for l in lines) else "확인 필요 항목 있음"
    return {"date": d, "headline": headline, "lines": lines, "failures": fails, "empty": False}
