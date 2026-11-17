"""주간/월간 리포트 (원본 형식 10섹션) — 기간 무관 코어 `period_report_data` + 주/월 경계 래퍼.

01 한 장 요약·계정 전체 · 02 좋아진 것·아쉬운 것 · 03 매체별 비교(+해석) · 04 구매 퍼널·단계별 이탈(GA4)
05 장바구니 담기 퍼널·상품별(카페24 접속통계) · 06 베스트 상품 · 07 고객 구성 · 08 자사몰 유입 검색어
09 네이버 검색·키워드 흐름 · 10 핵심 인사이트 & 다음 전략(편집용 초안)

주간: 지난주(월~일) vs 전주. `latest_complete_week` 는 데이터가 있는 완결 주로 폴백 → 탭이 지난주가 아닌 주를 보여주면 수집 구멍 신호.
월간: 전월 vs 전전월. 문구는 `prev_word`(전주/전월)로만 — 하드코딩 금지. 리포트는 빈 채로도 렌더되므로 `missing_dates` 를 먼저 볼 것.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date as _date, timedelta
from typing import Any

from . import breakdown
from .aggregate import compare, sum_range

WEEK_MIN_VIEWS = 50
MONTH_MIN_VIEWS = 200
SUMMARY_KEYS = ("gross_sales", "ad_cost", "ad_revenue", "roas", "orders", "aov", "conversion_rate", "visitors")
LABEL = {"gross_sales": "매출", "ad_cost": "광고비", "ad_revenue": "광고 매출", "roas": "ROAS", "orders": "주문건수", "aov": "객단가",
         "conversion_rate": "구매전환율", "visitors": "방문자", "ad_cost_ratio": "광고비율", "new_orders": "신규 주문",
         "returning_orders": "재구매 주문", "sessions": "세션", "ga4_conversions": "GA4 전환"}


def _won(v: float | None) -> str:
    return "—" if v is None else f"₩{v:,.0f}"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:+.1f}%"


def _x(v: float | None) -> str:
    return "—" if v is None else f"{v/100:.2f}x"


def _dates(f: str, t: str) -> list[str]:
    a, b = _date.fromisoformat(f), _date.fromisoformat(t)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def _md(d: str) -> str:
    return f"{int(d[5:7])}/{int(d[8:10])}"


def period_report_data(store, f: str, t: str, pf: str, pt: str, prev_word: str, min_views: int) -> dict[str, Any]:
    kpi_cur, kpi_prev = store.kpi_range(f, t), store.kpi_range(pf, pt)
    cur, prev = sum_range(kpi_cur), sum_range(kpi_prev)
    cmp = compare(cur, prev)
    missing = [d for d in _dates(f, t) if d not in kpi_cur]
    pct = lambda k: cmp.get(k, {}).get("pct")  # noqa: E731

    # 01 한 장 요약
    summary = {k: {"cur": cur.get(k), "prev": prev.get(k), "pct": pct(k)} for k in SUMMARY_KEYS + ("ad_cost_ratio", "new_orders", "returning_orders")}
    one_line = (f"{prev_word} 대비 매출 {_pct(pct('gross_sales'))} · 광고비 {_pct(pct('ad_cost'))} · ROAS {_pct(pct('roas'))}"
                f"({'개선' if (pct('roas') or 0) > 0 else '악화' if (pct('roas') or 0) < 0 else '유지'}).")

    # 03 매체별
    ch_cur = breakdown.ads_by_channel(store, f, t)
    ch_prev = {r["channel"]: r for r in breakdown.ads_by_channel(store, pf, pt)}
    channels = []
    for r in ch_cur:
        p = ch_prev.get(r["channel"], {})
        def cp(k: str) -> float | None:
            return ((r[k] - p[k]) / p[k] * 100) if (r.get(k) is not None and p.get(k)) else None
        channels.append({**r, "pct": {k: cp(k) for k in ("ad_cost", "ad_impressions", "ad_clicks", "ctr", "cpc", "ad_revenue", "roas", "ad_conversions")},
                         "prev": {k: p.get(k) for k in ("ad_cost", "ad_impressions", "ad_clicks", "ctr", "cpc", "ad_revenue", "roas", "ad_conversions", "cpa", "cvr")}})
    total_cost = sum((r["ad_cost"] or 0) for r in channels) or 1
    ch_note = ""
    if channels:
        top = channels[0]
        best_roas = max(channels, key=lambda r: r["roas"] or 0)
        ch_note = (f"{top['label']}가 예산 비중의 {top['ad_cost'] / total_cost * 100:.0f}%를 차지합니다"
                   + (f" (ROAS {_x(top['roas'])}, {prev_word} 대비 {_pct(top['pct']['roas'])})" if top.get("roas") is not None else "") + ". "
                   + (f"ROAS 가 가장 높은 채널은 {best_roas['label']}({_x(best_roas['roas'])})" + (" — 예산 재배분 검토." if best_roas is not top else " — 현재 집중이 적절합니다.") if best_roas.get("roas") else ""))

    # 04 GA4 퍼널
    funnel_ga4 = breakdown.ga4_funnel(store, f, t)
    if funnel_ga4.get("available"):
        pstep = {x["event"]: x for x in breakdown.ga4_funnel(store, pf, pt).get("steps", [])}
        for x in funnel_ga4["steps"]:
            pv = pstep.get(x["event"], {})
            x["prev_count"], x["prev_step_rate"] = pv.get("count"), pv.get("step_rate")

    # 05 담기 퍼널(상품별)
    fun, pfun = breakdown.cart_funnel(store, f, t, min_views), breakdown.cart_funnel(store, pf, pt, min_views)
    tc, tp = fun["totals"], pfun["totals"]
    cart = {"cart_rate": tc["cart_rate"], "order_rate": tc["order_rate"], "median_cart_rate": fun["median_cart_rate"],
            "views": tc["views"], "cart_adds": tc["cart_adds"], "orders": tc["orders"],
            "prev_cart_rate": tp["cart_rate"], "prev_order_rate": tp["order_rate"], "min_views": min_views,
            "prev_views": tp["views"], "prev_cart_adds": tp["cart_adds"], "prev_orders": tp["orders"], "prev_median_cart_rate": pfun["median_cart_rate"],
            "low_products": [r for r in fun["rows"] if r["bottleneck"] or r["cannot_add"]][:8]}

    # 06 베스트
    best = breakdown.best_products(store, f, t, top=10, pf=pf, pt=pt)  # prev_sales · prev_rank · pct 포함
    tot_sales = cur.get("gross_sales") or sum(b["sales"] for b in best) or 1
    for b in best:
        b["share"] = b["sales"] / tot_sales * 100

    # 07 고객 구성
    sa = breakdown.shop_analytics(store, f, t, pf, pt)
    members = {m["member_type"]: m for m in sa["members"]}
    mo, no = members.get("회원", {}), members.get("비회원", {})
    customers = {"new_sales": cur.get("new_sales"), "returning_sales": cur.get("returning_sales"), "returning_sales_share": cur.get("returning_sales_share"),
                 "new_orders": cur.get("new_orders"), "returning_orders": cur.get("returning_orders"),
                 "member_orders": mo.get("orders"), "member_aov": (mo["sales"] / mo["orders"]) if mo.get("orders") else None,
                 "guest_orders": no.get("orders"), "guest_aov": (no["sales"] / no["orders"]) if no.get("orders") else None,
                 "guest_share": (no.get("orders", 0) / (mo.get("orders", 0) + no.get("orders", 0)) * 100) if (mo.get("orders") or no.get("orders")) else None,
                 "mobile_share": cur.get("mobile_share"), "prev_mobile_share": prev.get("mobile_share")}

    # 07 비교표 — 이전 기간 값을 같이
    pm = {m["member_type"]: m for m in breakdown.shop_analytics(store, pf, pt)["members"]}
    pmo, pno = pm.get("회원", {}), pm.get("비회원", {})
    aov = lambda m: (m["sales"] / m["orders"]) if m.get("orders") else None  # noqa: E731
    def crow(label: str, unit: str, c: float | None, pv: float | None) -> dict[str, Any]:
        diff = (c - pv) if (unit.startswith("pct") and c is not None and pv is not None) else None
        return {"label": label, "unit": unit, "cur": c, "prev": pv, "pct": breakdown._pct(c, pv) if not unit.startswith("pct") else None, "diff": diff}
    customer_rows = [
        crow("신규 고객 매출", "krw", cur.get("new_sales"), prev.get("new_sales")),
        crow("재구매 고객 매출", "krw", cur.get("returning_sales"), prev.get("returning_sales")),
        crow("재구매 매출 비중", "pct1", cur.get("returning_sales_share"), prev.get("returning_sales_share")),
        crow("신규 주문", "count", cur.get("new_orders"), prev.get("new_orders")),
        crow("재구매 주문", "count", cur.get("returning_orders"), prev.get("returning_orders")),
        crow("회원 주문", "count", mo.get("orders"), pmo.get("orders")),
        crow("회원 객단가", "krw", aov(mo), aov(pmo)),
        crow("비회원 주문", "count", no.get("orders"), pno.get("orders")),
        crow("비회원 객단가", "krw", aov(no), aov(pno)),
        crow("모바일 매출 비중", "pct1", cur.get("mobile_share"), prev.get("mobile_share")),
    ]
    customer_rows = [r for r in customer_rows if r["cur"] is not None or r["prev"] is not None]

    # 카테고리 매출 (이전 기간 대비)
    categories = breakdown.category_sales(store, f, t, top=8, pf=pf, pt=pt)

    # 일별 매출·광고비 — 이번 기간과 이전 기간을 같은 칸(1일차, 2일차…)에 겹쳐 그리기 위한 값
    def daily(a: str, b: str, kp: dict[str, dict]) -> list[dict[str, Any]]:
        return [{"date": d, "gross_sales": (kp.get(d) or {}).get("gross_sales"), "ad_cost": (kp.get(d) or {}).get("ad_cost"),
                 "orders": (kp.get(d) or {}).get("orders")} for d in _dates(a, b)]
    daily_cmp = {"cur": daily(f, t, kpi_cur), "prev": daily(pf, pt, kpi_prev)}

    # 08 검색어 (비중·전주 대비·신규)
    keywords = sa["keywords"][:10]

    # 09 네이버 키워드 흐름
    nk = breakdown.keyword_report(store, f, t, sort="ad_cost", top=10)
    nk_prev = {k["keyword_id"]: k for k in breakdown.keyword_report(store, pf, pt, sort="ad_cost", top=1000)}
    for k in nk:
        pk = nk_prev.get(k["keyword_id"], {})
        k["prev"] = {m: pk.get(m) for m in ("ad_cost", "ad_clicks", "ctr", "cpc", "ad_conversions", "roas")}
        k["pct"] = {m: breakdown._pct(k.get(m), pk.get(m)) for m in ("ad_cost", "ad_clicks", "ad_conversions")}
        k["new"] = not pk
    nk_note = ""
    if nk:
        k0 = nk[0]
        nk_note = f"'{k0['keyword']}' 키워드가 파워링크 예산의 큰 비중을 차지합니다(광고비 {_won(k0['ad_cost'])}, 클릭 {k0['ad_clicks']:,.0f}, CTR {k0['ctr'] or 0:.2f}%). 전환 기여도를 확인해 확대·축소를 판단하세요."

    # 02 좋아진 것 · 아쉬운 것 (문장)
    better, worse = [], []
    if (pct("gross_sales") or 0) >= 5:
        better.append(f"매출 {_won(prev.get('gross_sales'))} → {_won(cur.get('gross_sales'))} ({_pct(pct('gross_sales'))}) — " + ("광고비 증가율보다 매출 증가율이 높아 효율 개선" if (pct("ad_cost") or 0) < (pct("gross_sales") or 0) else "매출 성장"))
    elif (pct("gross_sales") or 0) <= -5:
        worse.append(f"매출 {_won(prev.get('gross_sales'))} → {_won(cur.get('gross_sales'))} ({_pct(pct('gross_sales'))}) — 채널·품절·프로모션 요인 점검")
    if (pct("roas") or 0) >= 5:
        better.append(f"ROAS {_x(prev.get('roas'))} → {_x(cur.get('roas'))} ({_pct(pct('roas'))}) — 광고 1원당 매출 효율 개선")
    elif (pct("roas") or 0) <= -5:
        worse.append(f"ROAS {_x(prev.get('roas'))} → {_x(cur.get('roas'))} ({_pct(pct('roas'))}) — 채널별 ROAS 점검")
    if cart["cart_rate"] is not None and cart["prev_cart_rate"] is not None:
        d = cart["cart_rate"] - cart["prev_cart_rate"]
        (better if d >= 0 else worse).append(f"장바구니 담기율 {cart['cart_rate']:.2f}% · 담기→주문 {cart['order_rate'] or 0:.1f}% ({prev_word} 담기율 {cart['prev_cart_rate']:.2f}%, 조회 {cart['views']:,.0f}건 기준)")
    if customers["returning_sales_share"] is not None:
        better.append(f"재구매 매출 비중 {customers['returning_sales_share']:.1f}% (신규 {_won(customers['new_sales'])} · 재구매 {_won(customers['returning_sales'])})")
    new_kw = [k["keyword"] for k in keywords if k.get("new")]
    if new_kw:
        better.append("새로 유입된 검색어 — " + ", ".join(new_kw[:3]))
    if funnel_ga4.get("bottleneck"):
        worse.append(f"구매 퍼널 병목 — '{funnel_ga4['bottleneck']}' 단계 통과율이 가장 낮음")
    if customers["guest_share"] is not None and customers["guest_share"] >= 40:
        worse.append(f"비회원 주문 비중 {customers['guest_share']:.0f}% — 가입 유도(첫구매 혜택·CRM)로 재구매 연결 여지")
    if (pct("conversion_rate") or 0) <= -5:
        worse.append(f"구매전환율 {prev.get('conversion_rate') or 0:.2f}% → {cur.get('conversion_rate') or 0:.2f}% — 유입 품질·상세페이지 점검")

    # 10 핵심 인사이트 & 다음 전략 (편집용 초안)
    insights = []
    if funnel_ga4.get("bottleneck"):
        insights.append({"title": f"퍼널 병목 '{funnel_ga4['bottleneck']}' 단계를 한 주 동안 집중 점검한다",
                         "body": "해당 단계 직전 페이지의 이탈 요인(가격 노출·배송비 안내·옵션 UI·로딩 속도)을 한 가지씩만 바꿔 다음 주 수치와 비교합니다. 여러 개를 동시에 바꾸면 원인을 못 가립니다."})
    if channels:
        bst = max(channels, key=lambda r: r["roas"] or 0)
        insights.append({"title": "ROAS 개선 채널에 주 단위로 예산을 옮긴다",
                         "body": f"{bst['label']} ROAS {_x(bst['roas'])} 가 가장 높습니다. 전체 예산의 10~15%를 이 채널로 옮기고, 목표 ROAS 하한을 정해 넘으면 추가 증액, 못 넘으면 원복합니다."})
    insights.append({"title": "소재 CTR 피로도를 주 1회 로테이션으로 막는다",
                     "body": "CTR 이 떨어진 소재는 광고 히스토리 탭에서 '피로도 높음' 으로 표시됩니다. 베스트 상품·후기 영상 소재를 2~3종 준비해 주간 단위로 교체합니다."})
    insights.append({"title": "재구매·CRM 으로 객단가를 방어한다",
                     "body": (f"재구매 매출 비중 {customers['returning_sales_share']:.0f}%" if customers["returning_sales_share"] is not None else "재구매 매출") + " — 구매 후 7일 CRM(후기 요청·연관 상품 추천)과 회원 전환 혜택으로 재구매 비중을 높입니다."})
    if cart["low_products"]:
        p0 = cart["low_products"][0]
        insights.append({"title": f"담기율 낮은 상품 '{p0['product']}' 의 판매 가능 상태를 먼저 확인한다",
                         "body": "담기 0건은 인기 문제가 아니라 '담을 수 없는 상태'(전 옵션 품절·판매중지·옵션 미설정) 신호일 가능성이 큽니다. 광고가 이 상품으로 흐르고 있으면 즉시 중단합니다."})

    # 섹션별 코멘트 초안 — 화면에서 사용자가 고쳐 쓴다 (비교 숫자를 근거로 한 문장씩)
    def chg(label: str, k: str, fm) -> str:
        return f"{label} {fm(prev.get(k))} → {fm(cur.get(k))}({_pct(pct(k))})"
    comments: dict[str, str] = {}
    comments["summary"] = (f"{prev_word} 대비 " + ", ".join([chg("매출", "gross_sales", _won), chg("주문", "orders", lambda v: f"{v or 0:,.0f}건"), chg("객단가", "aov", _won)]) + ". "
                           + chg("광고비", "ad_cost", _won) + ", " + chg("ROAS", "roas", _x) + ".")
    comments["channels"] = ch_note
    if channels:
        ups = [c for c in channels if (c["pct"].get("roas") or 0) >= 10]
        dns = [c for c in channels if (c["pct"].get("roas") or 0) <= -10]
        if ups:
            comments["channels"] += " ROAS 개선: " + ", ".join(f"{c['label']}({_pct(c['pct']['roas'])})" for c in ups) + "."
        if dns:
            comments["channels"] += " ROAS 하락: " + ", ".join(f"{c['label']}({_pct(c['pct']['roas'])})" for c in dns) + " — 소재·입찰 점검."
    if funnel_ga4.get("available"):
        comments["funnel"] = funnel_ga4.get("note", "")
    if cart["cart_rate"] is not None:
        d = (cart["cart_rate"] - cart["prev_cart_rate"]) if cart["prev_cart_rate"] is not None else None
        comments["cart"] = (f"담기율 {cart['cart_rate']:.2f}%" + (f"({prev_word} {cart['prev_cart_rate']:.2f}%, {d:+.2f}%p)" if d is not None else "")
                            + f", 담기→주문 {cart['order_rate'] or 0:.1f}%" + (f"({prev_word} {cart['prev_order_rate']:.1f}%)" if cart["prev_order_rate"] is not None else "") + ". "
                            + (f"담기율이 낮은 상품 {len(cart['low_products'])}개는 품절·옵션 상태부터 확인." if cart["low_products"] else "담기율 경고 상품 없음."))
    if categories:
        c0 = categories[0]
        up = max(categories, key=lambda c: c["sales"] - (c["prev_sales"] or 0)); dn = min(categories, key=lambda c: c["sales"] - (c["prev_sales"] or 0))
        comments["categories"] = (f"{c0['category']}가 매출의 {c0['share']:.0f}%로 1위. "
                                  + (f"가장 많이 늘어난 카테고리는 {up['category']}({_won(up['sales'] - (up['prev_sales'] or 0))} 증가)" if up["sales"] > (up["prev_sales"] or 0) else "증가한 카테고리 없음")
                                  + (f", 가장 많이 줄어든 카테고리는 {dn['category']}({_won((dn['prev_sales'] or 0) - dn['sales'])} 감소)." if dn["sales"] < (dn["prev_sales"] or 0) else "."))
    if best:
        newb = [b["product"] for b in best if b.get("prev_rank") is None]
        riser = [b for b in best if b.get("prev_rank") and b["prev_rank"] - b["rank"] >= 3]
        comments["best"] = (f"1위 {best[0]['product']}({_won(best[0]['sales'])}, 매출의 {best[0]['share']:.1f}%). "
                            + (f"순위 급상승: {', '.join(b['product'] for b in riser[:3])}. " if riser else "")
                            + (f"새로 진입: {', '.join(newb[:3])}." if newb else ""))
    if customers["returning_sales_share"] is not None:
        ps = prev.get("returning_sales_share")
        comments["customers"] = (f"재구매 매출 비중 {customers['returning_sales_share']:.1f}%" + (f"({prev_word} {ps:.1f}%)" if ps is not None else "") + ". "
                                 + chg("신규 주문", "new_orders", lambda v: f"{v or 0:,.0f}건") + ", " + chg("재구매 주문", "returning_orders", lambda v: f"{v or 0:,.0f}건") + ".")
    if keywords:
        comments["keywords"] = (f"유입 1위 검색어 '{keywords[0]['keyword']}'(비중 {keywords[0]['share']:.1f}%). "
                                + (f"새로 등장: {', '.join(new_kw[:5])}." if new_kw else "새로 등장한 검색어 없음."))
    if nk:
        comments["naver_keywords"] = nk_note

    return {
        "comments": comments, "customer_rows": customer_rows, "daily_cmp": daily_cmp,
        "range": {"from": f, "to": t}, "prev_range": {"from": pf, "to": pt}, "prev_word": prev_word,
        "one_line": one_line, "missing_dates": missing, "empty": not kpi_cur,
        "summary": summary, "better": better, "worse": worse,
        "channels": channels, "channel_note": ch_note, "funnel_ga4": funnel_ga4, "cart": cart,
        "best": best, "customers": customers, "keywords": keywords, "naver_keywords": nk, "naver_note": nk_note,
        "insights": insights[:4], "ga4_channels": breakdown.ga4_channels(store, f, t, top=8),
        "categories": categories,
    }


# ---------------- 주간 ----------------
def week_bounds(any_day: str) -> tuple[str, str]:
    d = _date.fromisoformat(any_day)
    mon = d - timedelta(days=d.weekday())
    return mon.isoformat(), (mon + timedelta(days=6)).isoformat()


def latest_complete_week(store, today: str | None = None) -> tuple[str, str]:
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
    data.update({"kind": "weekly", "title": f"{_md(pf)}~{_md(pt)} 주 → {_md(f)}~{_md(t)} 주 성과 비교",
                 "cur_label": f"{_md(f)}~{_md(t)} 주", "prev_label": f"{_md(pf)}~{_md(pt)} 주",
                 "subtitle": f"매출·ROAS · 구매 퍼널 · 장바구니 담기 병목 중심 · {f} ~ {t}",
                 "note": "매주 월요일 오전 9시, 발송 전 지난주(월~일) 리포트가 이 화면에 자동으로 갱신됩니다. 표·증감·좋아진/아쉬운 항목은 데이터로 자동 작성되며, 한 번에 전략을 편집해 보고에 활용하세요."})
    return data


# ---------------- 월간 ----------------
def month_bounds(ym: str) -> tuple[str, str]:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{monthrange(y, m)[1]:02d}"


def latest_complete_month(today: str | None = None) -> str:
    d = _date.fromisoformat(today) if today else _date.today()
    return (d.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def monthly_report(store, month: str | None = None, today: str | None = None) -> dict[str, Any]:
    ym = month or latest_complete_month(today)
    f, t = month_bounds(ym)
    prev_ym = (_date.fromisoformat(f) - timedelta(days=1)).strftime("%Y-%m")
    pf, pt = month_bounds(prev_ym)
    data = period_report_data(store, f, t, pf, pt, "전월", MONTH_MIN_VIEWS)
    data.update({"kind": "monthly", "title": f"{int(prev_ym[5:7])}월 → {int(ym[5:7])}월 성과 비교",
                 "cur_label": f"{int(ym[5:7])}월", "prev_label": f"{int(prev_ym[5:7])}월",
                 "subtitle": f"온라인광고 컨설턴트 관점 월간 브리핑 · {f} ~ {t}",
                 "note": "매월 1일이 되면 전월 확정분 리포트가 자동으로 표시됩니다. Word 로 내려받아 편집·보고에 활용하세요."})
    return data
