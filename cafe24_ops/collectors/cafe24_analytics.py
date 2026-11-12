"""카페24 통계 API 수집기 — 접속통계 9블록.

방문/신규/재방문 · 상품별 조회→담기 · 상품별 주문/수량/금액 · 유입 검색어 · 유입 도메인 · 광고채널 방문 · 페이지뷰 · 회원/비회원.
블록 하나의 실패는 부분 실패로만 기록(보조 지표가 하루 수집 전체를 막으면 안 된다). 전부 실패면 예외.
응답 구조는 clients/cafe24_analytics.py 상단 '실측 응답 구조' 참고."""
from __future__ import annotations

from typing import Any, Callable

from ..clients import cafe24_client as cc
from ..clients.cafe24_analytics import Cafe24Analytics, _num
from .base import Fact, PartialFailure, fact

SRC = "cafe24_analytics"
# 무료 DB(Neon 0.5GB) 용량 관리 — 일자별 저장 행 수 상한 (2025-01-01~ 누적 기준 수십만 행 이내)
TOP_PRODUCTS = 100   # 상품 퍼널: 조회 상위 N개 + 주문 상위 TOP_SOLD 개
TOP_SOLD = 50
TOP_KEYWORDS, TOP_DOMAINS, TOP_PAGES = 100, 50, 30


def _name(names: dict[str, str], no: str, cand: str) -> str:
    """같은 상품이 페이지 제목 등 여러 이름으로 오므로 '[품번]' 이 들어간 이름을 우선."""
    cur = names.get(no)
    if not cur or ("[" not in cur and "[" in (cand or "")):
        names[no] = cand or cur or no
    return names[no]


def _blocks(an: Cafe24Analytics, d: str) -> list[tuple[str, Callable[[], list[Fact]]]]:
    names: dict[str, str] = {}

    def visitors() -> list[Fact]:
        v = an.visitors_view(d)
        return [fact(d, SRC, "visit_count", v["visit_count"]), fact(d, SRC, "first_visit_count", v["first_visit_count"]),
                fact(d, SRC, "re_visit_count", v["re_visit_count"])]

    def products() -> list[Fact]:
        """상품별 조회(products/view) · 담기(carts/action) · 주문/수량/금액(products/sales) 를 상품번호로 합친다."""
        views: dict[str, float] = {}
        adds: dict[str, float] = {}
        sales: dict[str, dict[str, float]] = {}
        errs = []
        try:
            for r in an.products_view(d, d):
                no = str(r.get("product_no", ""))
                _name(names, no, r.get("product_name", ""))
                views[no] = views.get(no, 0) + _num(r.get("count") or r.get("view_count"))
        except Exception as e:  # noqa: BLE001
            errs.append(f"products/view: {e}")
        cart_views: dict[str, float] = {}
        try:
            for r in an.carts_action(d, d):
                no = str(r.get("product_no", ""))
                _name(names, no, r.get("product_name", ""))
                cart_views[no] = cart_views.get(no, 0) + _num(r.get("count") or r.get("view_count"))
                adds[no] = max(adds.get(no, 0), _num(r.get("add_cart_count")))
        except Exception as e:  # noqa: BLE001
            errs.append(f"carts/action: {e}")
        try:
            for r in an.products_sales(d, d):
                no = str(r.get("product_no", ""))
                _name(names, no, r.get("product_name", ""))
                s = sales.setdefault(no, {"product_orders": 0, "product_qty": 0, "product_amount": 0})
                s["product_orders"] += _num(r.get("order_count"))
                s["product_qty"] += _num(r.get("order_product_count") or r.get("order_quantity") or r.get("quantity"))
                s["product_amount"] += _num(r.get("order_amount"))
        except Exception as e:  # noqa: BLE001
            errs.append(f"products/sales: {e}")
        if len(errs) == 3:
            raise RuntimeError(" | ".join(errs))
        for no, v in cart_views.items():  # products/view 실패·누락 상품은 담기 응답의 조회 합계로 보완
            views.setdefault(no, v)
        keep = sorted(views, key=lambda n: -views[n])[:TOP_PRODUCTS]
        keep = list(dict.fromkeys(keep + sorted(sales, key=lambda n: -sales[n]["product_orders"])[:TOP_SOLD]))
        out: list[Fact] = []
        for no in keep:
            dims = {"product_no": no, "product": names.get(no, no)}
            out.append(fact(d, SRC, "product_views", views.get(no, 0), **dims))
            out.append(fact(d, SRC, "product_cart_adds", adds.get(no, 0), **dims))
            for k, v in sales.get(no, {}).items():
                if v:
                    out.append(fact(d, SRC, k, v, **dims))
        return out

    def keywords() -> list[Fact]:
        return [fact(d, SRC, "keyword_visits", _num(r.get("visit_count") or r.get("count")), keyword=r.get("keyword", ""))
                for r in an.keywords(d, d)[:TOP_KEYWORDS] if r.get("keyword")]

    def domains() -> list[Fact]:
        return [fact(d, SRC, "domain_visits", _num(r.get("visit_count") or r.get("count")), domain=r.get("domain", ""))
                for r in an.domains(d, d)[:TOP_DOMAINS] if r.get("domain")]

    def adpaths() -> list[Fact]:
        agg: dict[str, float] = {}
        for r in an.ad_paths(d, d):
            name = r.get("ad") or r.get("ad_name") or r.get("ad_channel") or r.get("name") or "기타"
            agg[name] = agg.get(name, 0) + _num(r.get("visit_count") or r.get("count"))
        return [fact(d, SRC, "adpath_visits", v, ad_channel=k) for k, v in agg.items()]

    def pages() -> list[Fact]:
        out = []
        for r in an.pages_view(d, d)[:TOP_PAGES]:
            path = r.get("url") or r.get("page_url") or ""
            if path:
                out.append(fact(d, SRC, "page_views", _num(r.get("count") or r.get("view_count")), path=path))
        return out

    def members() -> list[Fact]:
        out = []
        for r in an.members_sales(d, d):
            if "member_order_count" in r or "nonmember_order_count" in r:  # 실측: 1행에 회원/비회원 컬럼
                for t, pre in (("회원", "member"), ("비회원", "nonmember")):
                    out.append(fact(d, SRC, "member_orders", _num(r.get(f"{pre}_order_count")), member_type=t))
                    out.append(fact(d, SRC, "member_sales", _num(r.get(f"{pre}_order_amount")), member_type=t))
                continue
            t = "회원" if str(r.get("member_type", r.get("type", ""))).lower() in ("member", "m", "회원") else "비회원"
            out.append(fact(d, SRC, "member_orders", _num(r.get("order_count")), member_type=t))
            out.append(fact(d, SRC, "member_sales", _num(r.get("order_amount")), member_type=t))
        return out

    return [("visitors/view", visitors), ("products(view·carts·sales)", products),
            ("visitpaths/keywords", keywords), ("visitpaths/domains", domains), ("visitpaths/ads", adpaths),
            ("pages/view", pages), ("members/sales", members)]


def collect(store, d: str) -> list[Fact]:
    an = Cafe24Analytics(cc.Cafe24Client.from_store(store))
    out: list[Fact] = []
    errors: list[str] = []
    for name, fn in _blocks(an, d):
        try:
            out += fn()
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    if errors and not out:
        raise RuntimeError("cafe24_analytics 전부 실패: " + " | ".join(errors))
    if errors:
        raise PartialFailure(out, errors)
    return out
