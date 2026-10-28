"""카페24 Admin API 수집기 — 주문·매출·신규/재구매·디바이스·상품별 매출."""
from __future__ import annotations

from collections import defaultdict

from ..clients import cafe24_client as cc
from .base import Fact, fact


def _f(v) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def collect(store, d: str) -> list[Fact]:
    client = cc.Cafe24Client.from_store(store)  # 반드시 from_store (토큰 회전 영속)
    orders = client.orders(d, d, embed="items")
    gross = n = new = mobile_n = canceled = 0
    mobile_sales = new_sales = 0.0
    prod_sales: dict[tuple[str, str, str], float] = defaultdict(float)
    for o in orders:
        if o.get("canceled") == "T":
            canceled += 1
            continue
        amt = _f(o.get("payment_amount"))
        if not amt and isinstance(o.get("actual_order_amount"), dict):
            amt = _f(o["actual_order_amount"].get("payment_amount"))
        n += 1
        gross += amt
        if o.get("first_order") == "T":
            new += 1
            new_sales += amt
        if o.get("order_from_mobile") == "T":
            mobile_n += 1
            mobile_sales += amt
        for it in o.get("items") or []:
            cat = ""
            fc = it.get("full_category_name")
            if isinstance(fc, dict) and fc:
                cat = list(fc.values())[-1] or ""
            key = (str(it.get("product_no", "")), it.get("product_name", ""), cat)
            prod_sales[key] += _f(it.get("product_price")) * _f(it.get("quantity") or 1)
    out = [
        fact(d, "cafe24", "gross_sales", gross),
        fact(d, "cafe24", "orders", n),
        fact(d, "cafe24", "new_orders", new),
        fact(d, "cafe24", "returning_orders", n - new),
        fact(d, "cafe24", "mobile_sales", mobile_sales),
        fact(d, "cafe24", "pc_sales", gross - mobile_sales),
        fact(d, "cafe24", "mobile_orders", mobile_n),
        fact(d, "cafe24", "pc_orders", n - mobile_n),
        fact(d, "cafe24", "canceled_orders", canceled),
        fact(d, "cafe24", "new_sales", new_sales),
        fact(d, "cafe24", "returning_sales", gross - new_sales),
    ]
    try:  # 품절(판매 중지) 상품 수 — 실 키로 파라미터 1회 검증 권장
        out.append(fact(d, "cafe24", "soldout_products", client.products_count(selling="F")))
    except Exception:  # noqa: BLE001
        pass
    for (no, name, cat), v in prod_sales.items():
        out.append(fact(d, "cafe24", "product_sales", v, product_no=no, product=name, category=cat))
    return out
