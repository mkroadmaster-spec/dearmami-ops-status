"""카페24 통계(Analytics) API — Admin API 와 호스트가 다르다.

호스트: https://ca-api.cafe24data.com  (경로 접두어 없음)
인증 : Admin 과 같은 OAuth 토큰, 단 `mall.read_analytics` scope 필수(없으면 전부 403 INVALID SCOPE).

실측 확정 경로 (추측으로 다른 경로 호출하지 말 것 — skills/카페24-운영현황/SKILL.md):
  /carts/action        상품별 조회→담기→담기율 (구매 퍼널 핵심)
  /products/sales      상품별 주문수·수량·매출
  /products/view       상품별 조회수
  /visitpaths/keywords 자연 검색 실제 검색어
  /visitpaths/domains  유입 도메인
  /visitpaths/ads      광고 채널별 방문
  /visitors/view       일자별 방문/신규/재방문
  /pages/view          페이지 URL별 조회/방문
  /members/sales       회원/비회원 주문수·금액
없는 경로(확인됨): /carts/view, /sales/*, /orders/*, /members/view, /adeffect/*,
  /visitors/hours|devices|newandreturn, /pages/exit|entrance, /products/buy|carts|best
숫자가 문자열로 오는 필드가 섞여 있다 ("order_amount": "1908000").

실측 응답 구조 (2026-11 확인):
  /visitors/view      {"view": [{date, visit_count, first_visit_count, re_visit_count}]}
  /carts/action       {"action": [{product_no, product_name, count(조회), add_cart_count, add_cart_rate}]}
                       ※ 같은 상품이 이름(페이지 제목) 별로 여러 행 — 조회는 합산, 담기는 상품 단위 값이 반복(최대값 사용)
  /products/sales     {"sales": [{product_no, product_name, order_count, order_product_count(수량), order_amount}]}
  /products/view      {"view": [{product_no, product_name, count}]}
  /visitpaths/keywords {"keywords": [{keyword, visit_count}]}   /visitpaths/domains {"domains": [{domain, visit_count}]}
  /visitpaths/ads     {"ads": [{ad, visit_count}]}
  /pages/view         {"view": [{url, count, visit_count, first_visit_count}]}
  /members/sales      {"sales": [{member_order_count, member_order_amount, nonmember_order_count, nonmember_order_amount}]}
  목록은 기본 100행 → limit=1000 지원 (offset 도 지원).
"""
from __future__ import annotations

import time
from typing import Any

HOST = "https://ca-api.cafe24data.com"
LIMIT = 1000


def _num(v: Any) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _rows(data: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    """응답의 목록 키가 경로마다 다르다(view/action/sales/…) → 지정 키 우선, 없으면 첫 목록 값."""
    for k in keys:
        if isinstance(data.get(k), list):
            return data[k]
    return next((v for v in data.values() if isinstance(v, list)), [])


class Cafe24Analytics:
    def __init__(self, cafe24_client):
        self.c = cafe24_client  # Cafe24Client (토큰 공유·갱신 위임)

    def get(self, path: str, start_date: str, end_date: str, **params) -> dict[str, Any]:
        if self.c.expires_at and time.time() >= self.c.expires_at:
            self.c._refresh_now()
        q = {"mall_id": self.c.mall_id, "start_date": start_date, "end_date": end_date, **params}
        r = self.c._get_retry(f"{HOST}{path}", q)
        if r.status_code == 401:
            self.c._refresh_now()
            r = self.c._get_retry(f"{HOST}{path}", q)
        if r.status_code == 403:
            raise PermissionError(f"analytics {path} 403 — mall.read_analytics scope 누락 가능: {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"analytics GET {path} {r.status_code}: {r.text[:300]}")
        return r.json()

    def visitors_view(self, d: str) -> dict[str, float]:
        tot = {"visit_count": 0.0, "first_visit_count": 0.0, "re_visit_count": 0.0}
        for r in _rows(self.get("/visitors/view", d, d), "view"):
            for k in tot:
                tot[k] += _num(r.get(k))
        return tot

    def carts_action(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/carts/action", s, e, limit=LIMIT), "action")

    def products_sales(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/products/sales", s, e, limit=LIMIT), "sales")

    def products_view(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/products/view", s, e, limit=LIMIT), "view")

    def keywords(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/visitpaths/keywords", s, e, limit=LIMIT), "keywords")

    def domains(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/visitpaths/domains", s, e, limit=LIMIT), "domains")

    def ad_paths(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/visitpaths/ads", s, e, limit=LIMIT), "ads")

    def pages_view(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/pages/view", s, e, limit=LIMIT), "view")

    def members_sales(self, s: str, e: str) -> list[dict[str, Any]]:
        return _rows(self.get("/members/sales", s, e), "sales")
