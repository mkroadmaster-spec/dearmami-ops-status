"""카페24 통계 API 수집기 — 접속통계 9블록.

방문/신규/재방문 · 상품별 조회→담기 · 상품별 주문/수량 · 유입 검색어 · 유입 도메인 · 광고채널 방문 · 페이지뷰 · 회원/비회원.
블록 하나의 실패는 부분 실패로만 기록(보조 지표가 하루 수집 전체를 막으면 안 된다). 전부 실패면 예외."""
from __future__ import annotations

from typing import Any, Callable

from ..clients import cafe24_client as cc
from ..clients.cafe24_analytics import Cafe24Analytics, _num
from .base import Fact, PartialFailure, fact

SRC = "cafe24_analytics"


def _blocks(an: Cafe24Analytics, d: str) -> list[tuple[str, Callable[[], list[Fact]]]]:
    def visitors() -> list[Fact]:
        v = an.visitors_view(d)
        return [fact(d, SRC, "visit_count", v["visit_count"]), fact(d, SRC, "first_visit_count", v["first_visit_count"]),
                fact(d, SRC, "re_visit_count", v["re_visit_count"])]

    def carts() -> list[Fact]:
        out = []
        for r in an.carts_action(d, d):
            no, name = str(r.get("product_no", "")), r.get("product_name", "")
            out.append(fact(d, SRC, "product_views", _num(r.get("view_count")), product_no=no, product=name))
            out.append(fact(d, SRC, "product_cart_adds", _num(r.get("add_cart_count")), product_no=no, product=name))
        return out

    def psales() -> list[Fact]:
        out = []
        for r in an.products_sales(d, d):
            no, name = str(r.get("product_no", "")), r.get("product_name", "")
            out.append(fact(d, SRC, "product_orders", _num(r.get("order_count")), product_no=no, product=name))
            out.append(fact(d, SRC, "product_qty", _num(r.get("order_quantity") or r.get("quantity")), product_no=no, product=name))
        return out

    def keywords() -> list[Fact]:
        return [fact(d, SRC, "keyword_visits", _num(r.get("visit_count") or r.get("count")), keyword=r.get("keyword", ""))
                for r in an.keywords(d, d)]

    def domains() -> list[Fact]:
        return [fact(d, SRC, "domain_visits", _num(r.get("visit_count") or r.get("count")), domain=r.get("domain", ""))
                for r in an.domains(d, d)]

    def adpaths() -> list[Fact]:
        return [fact(d, SRC, "adpath_visits", _num(r.get("visit_count") or r.get("count")),
                     ad_channel=r.get("ad_name") or r.get("ad_channel") or r.get("name", ""))
                for r in an.ad_paths(d, d)]

    def pages() -> list[Fact]:
        return [fact(d, SRC, "page_views", _num(r.get("view_count") or r.get("count")), path=r.get("page_url") or r.get("url", ""))
                for r in an.pages_view(d, d)[:50]]

    def members() -> list[Fact]:
        out = []
        for r in an.members_sales(d, d):
            t = "회원" if str(r.get("member_type", r.get("type", ""))).lower() in ("member", "m", "회원") else "비회원"
            out.append(fact(d, SRC, "member_orders", _num(r.get("order_count")), member_type=t))
            out.append(fact(d, SRC, "member_sales", _num(r.get("order_amount")), member_type=t))
        return out

    return [("visitors/view", visitors), ("carts/action", carts), ("products/sales", psales),
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
