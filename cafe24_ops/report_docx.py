"""주간·월간 리포트 Word(.docx) — period_report_data 10섹션을 그대로 문서화 (python-docx)."""
from __future__ import annotations

import io
from typing import Any

from docx import Document
from docx.shared import Pt

from . import config
from .etl.period_report import LABEL, _pct, _won, _x


def _fmt(k: str, v: float | None) -> str:
    if v is None:
        return "—"
    if k in ("gross_sales", "aov", "ad_cost", "ad_revenue", "cpc", "cpa", "sales", "new_sales", "returning_sales"):
        return _won(v)
    if k == "roas":
        return _x(v)
    if k in ("conversion_rate", "ad_cost_ratio", "ctr", "cvr", "cart_rate", "mobile_share", "share"):
        return f"{v:.2f}%"
    return f"{v:,.0f}"


def _table(doc, header: list[str], rows: list[list[Any]]) -> None:
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = str(h)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = str(v)
    doc.add_paragraph()


def build(d: dict[str, Any]) -> bytes:
    brand = config.sources().get("brand", "")
    pw, cl, pl = d["prev_word"], d.get("cur_label", "이번 기간"), d.get("prev_label", d["prev_word"])
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_heading(f"{brand} · {d['title']}", 0)
    doc.add_paragraph(d.get("subtitle", ""))
    doc.add_paragraph("한 문장 요약 — " + d["one_line"])
    if d.get("missing_dates"):
        doc.add_paragraph(f"⚠ 수집 누락일: {', '.join(d['missing_dates'])}")

    doc.add_heading("01 한 장 요약 · 계정 전체", 1)
    _table(doc, ["지표", pl, cl, "증감"], [[LABEL.get(k, k), _fmt(k, v["prev"]), _fmt(k, v["cur"]), _pct(v["pct"])]
                                          for k, v in d["summary"].items() if v["cur"] is not None][:8])

    doc.add_heading("02 좋아진 것 · 아쉬운 것", 1)
    doc.add_paragraph("◆ 개선된 지표")
    for s in d["better"] or ["—"]:
        doc.add_paragraph(s, style="List Bullet")
    doc.add_paragraph("◆ 아쉬운 · 점검할 지표")
    for s in d["worse"] or ["—"]:
        doc.add_paragraph(s, style="List Bullet")

    if d["channels"]:
        doc.add_heading(f"03 매체별 비교 ({pl} → {cl})", 1)
        _table(doc, ["채널", "광고비", "노출", "클릭", "CTR", "CPC", "광고매출", "ROAS"],
               [[r["label"], f"{_won(r['ad_cost'])} ({_pct(r['pct']['ad_cost'])})", f"{r['ad_impressions']:,.0f}", f"{r['ad_clicks']:,.0f}",
                 f"{r['ctr'] or 0:.2f}%", _won(r["cpc"]), _won(r["ad_revenue"]), f"{_x(r['roas'])} ({_pct(r['pct']['roas'])})"] for r in d["channels"]])
        doc.add_paragraph("해석 — " + d["channel_note"])

    fg = d["funnel_ga4"]
    if fg.get("available"):
        doc.add_heading(f"04 구매 퍼널 · 단계별 이탈 (GA4, {cl})", 1)
        _table(doc, ["단계", "건수", "직전 단계 대비", "첫 단계 대비", "이탈"],
               [[s["label"] + (" ★병목" if s["label"] == fg["bottleneck"] else ""), f"{s['count']:,.0f}",
                 "—" if s["step_rate"] is None else f"{s['step_rate']:.1f}%", "—" if s["first_rate"] is None else f"{s['first_rate']:.2f}%",
                 "—" if s["drop"] is None else f"-{s['drop']:,.0f}"] for s in fg["steps"]])
        doc.add_paragraph("병목 — " + fg["note"] + " GA4 는 개별 사용자 경로가 아니라 단계별 이벤트 건수 감소로 보는 값입니다.")

    c = d["cart"]
    if c["views"]:
        doc.add_heading(f"05 장바구니 담기 퍼널 · 상품별 (카페24 접속통계, {cl})", 1)
        _table(doc, ["조회 → 담기", "담기 → 주문", "상품 담기율 중위값", "집계 대상 조회"],
               [[_fmt("cart_rate", c["cart_rate"]), _fmt("cart_rate", c["order_rate"]), _fmt("cart_rate", c["median_cart_rate"]), f"{c['views']:,.0f}"]])
        doc.add_paragraph(f"담기율이 중위값 절반 미만이면 병목으로 봅니다. ({pw} 조회→담기 {_fmt('cart_rate', c['prev_cart_rate'])})")
        if c["low_products"]:
            _table(doc, ["담기율 낮은 상품", "조회", "담기", "담기율", "상태"],
                   [[p["product"], f"{p['views']:,.0f}", f"{p['cart_adds']:,.0f}", _fmt("cart_rate", p["cart_rate"]),
                     "담을 수 없는 상태?" if p["cannot_add"] else "병목"] for p in c["low_products"]])

    if d["best"]:
        doc.add_heading(f"06 베스트 상품 ({cl})", 1)
        _table(doc, ["상품", "매출", "매출 비중", f"{pw} 순위"], [[b["product"], _won(b["sales"]), f"{b['share']:.1f}%", b["prev_rank"] or "신규"] for b in d["best"]])

    cu = d["customers"]
    doc.add_heading(f"07 고객 구성 · 신규/재구매 · 회원/비회원 ({cl})", 1)
    _table(doc, ["구분", "값"], [["신규 고객 매출", _won(cu["new_sales"])], ["재구매 고객 매출", _won(cu["returning_sales"])],
                               ["재구매 매출 비중", _fmt("share", cu["returning_sales_share"])],
                               ["회원 주문", f"{cu['member_orders'] or 0:,.0f} 건 · 객단가 {_won(cu['member_aov'])}"],
                               ["비회원 주문", f"{cu['guest_orders'] or 0:,.0f} 건 · 객단가 {_won(cu['guest_aov'])}"],
                               ["비회원 주문 비중", _fmt("share", cu["guest_share"])], ["모바일 매출 비중", _fmt("share", cu["mobile_share"])]])

    if d["keywords"]:
        doc.add_heading(f"08 자사몰 유입 검색어 (카페24 접속통계, {cl})", 1)
        _table(doc, ["검색어", "방문", "비중", f"{pw} 대비", "신규"],
               [[k["keyword"], f"{k['visits']:,.0f}", f"{k['share']:.1f}%", "—" if k["prev"] is None else f"{k['prev']:,.0f}", "★" if k["new"] else ""] for k in d["keywords"]])

    if d["naver_keywords"]:
        doc.add_heading(f"09 네이버 검색 · 키워드 흐름 ({cl})", 1)
        _table(doc, ["키워드", "캠페인", "광고비", "클릭", "CTR", "CPC"],
               [[k["keyword"], f"{k['campaign']} · {k['adgroup']}", _won(k["ad_cost"]), f"{k['ad_clicks']:,.0f}", f"{k['ctr'] or 0:.2f}%", _won(k["cpc"])] for k in d["naver_keywords"]])
        doc.add_paragraph(d["naver_note"])

    doc.add_heading("10 핵심 인사이트 & 다음 전략 (편집용 초안)", 1)
    for i, ins in enumerate(d["insights"], 1):
        doc.add_paragraph(f"{i}. {ins['title']}", style="List Number")
        doc.add_paragraph(ins["body"])
    doc.add_paragraph("※ 전략은 초안입니다. 편집해 보고에 활용하세요.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
