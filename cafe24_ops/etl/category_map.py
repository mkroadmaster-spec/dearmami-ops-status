"""상품번호 → 대시보드 카테고리 그룹 매핑 (카페24 Admin API).

주문 품목(items)에는 카테고리가 없어서(전부 '기타'로 보이던 원인) 상품 상세의 category 목록 + 카테고리 트리로 판정한다.
결과는 DB(app_kv 'cafe24_product_category')에 쌓아 두고 집계할 때 상품번호로 붙인다 → 과거 매출도 재수집 없이 분류된다.
상품의 원본 카테고리 번호도 같이 보관(app_kv 'cafe24_product_catnos') → category_groups 를 바꾼 뒤 reclassify() 로 다시 분류.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .. import config

KV = "cafe24_product_category"
KV_RAW = "cafe24_product_catnos"   # 상품번호 → [카테고리 번호] (그룹 정의를 바꿨을 때 API 재조회 없이 다시 분류)
_tree: dict[int, list[str]] | None = None  # category_no → [깊은 단계 → 얕은 단계 이름]


def groups() -> dict[str, list[str]]:
    return {k: list(v or []) for k, v in (config.metrics().get("category_groups") or {}).items()}


def _clean(name: str | None) -> str:
    return re.sub(r"<[^>]+>", "", name or "").strip()


def load(store) -> dict[str, str]:
    try:
        return json.loads(store.kv_get(KV) or "{}")
    except ValueError:
        return {}


def classify(cat_nos: list[int], tree: dict[int, list[str]], grp: dict[str, list[str]] | None = None) -> str:
    grp = grp or groups()
    order = list(grp)
    name_to = {}
    for g, names in grp.items():
        for n in [g, *names]:
            name_to.setdefault(n, g)
    votes: Counter = Counter()
    for no in cat_nos:
        for n in tree.get(int(no), []):  # 깊은 단계부터
            if n in name_to:
                votes[name_to[n]] += 1
                break
    if not votes:
        return "기타"
    return sorted(votes, key=lambda g: (-votes[g], order.index(g) if g in order else 99))[0]


def _load_tree(client) -> dict[int, list[str]]:
    global _tree
    if _tree is None:
        cats, off = [], 0
        while True:
            ch = client.get("/admin/categories", {"limit": 100, "offset": off}).get("categories", [])
            cats += ch
            if len(ch) < 100:
                break
            off += 100
        _tree = {}
        for c in cats:
            fn = c.get("full_category_name") or {}
            path = [_clean(fn.get(str(i))) for i in range(1, 5) if fn.get(str(i))]
            _tree[int(c["category_no"])] = list(reversed(path)) or [_clean(c.get("category_name"))]
    return _tree


def _categories_of(client, nos: list[str]) -> dict[str, list[int]]:
    """여러 상품의 category 목록. 목록 API 에 category 가 없으면 상품 상세로."""
    out: dict[str, list[int]] = {}
    for i in range(0, len(nos), 100):
        chunk = nos[i:i + 100]
        items = client.get("/admin/products", {"product_no": ",".join(chunk), "limit": 100}).get("products", [])
        for p in items:
            if "category" in p:
                out[str(p["product_no"])] = [int(c["category_no"]) for c in (p.get("category") or []) if c.get("category_no")]
    for no in nos:
        if no not in out:
            p = (client.get(f"/admin/products/{no}", {}) or {}).get("product") or {}
            out[no] = [int(c["category_no"]) for c in (p.get("category") or []) if c.get("category_no")]
    return out


def _load_raw(store) -> dict[str, list[int]]:
    try:
        return json.loads(store.kv_get(KV_RAW) or "{}")
    except ValueError:
        return {}


def ensure(store, client, product_nos: list[str] | set[str]) -> dict[str, str]:
    """처음 보는 상품만 조회해 매핑에 추가. 반환: 전체 매핑."""
    mp = load(store)
    todo = sorted({str(n) for n in product_nos if n and str(n) not in mp})
    if not todo:
        return mp
    tree = _load_tree(client)
    grp = groups()
    raw = _load_raw(store)
    for no, cats in _categories_of(client, todo).items():
        raw[no] = cats
        mp[no] = classify(cats, tree, grp)
    store.kv_set(KV_RAW, json.dumps(raw))
    store.kv_set(KV, json.dumps(mp, ensure_ascii=False))
    return mp


def reclassify(store, client) -> dict[str, str]:
    """category_groups 를 고친 뒤 전체 상품을 다시 분류. 원본 카테고리 번호가 보관된 상품은 API 재조회 없이,
    없는 상품(예전에 채운 것)만 다시 조회한다. 반환: 전체 매핑."""
    mp = load(store)
    raw = _load_raw(store)
    tree = _load_tree(client)
    grp = groups()
    missing = sorted(n for n in mp if n not in raw)
    if missing:
        raw.update(_categories_of(client, missing))
        store.kv_set(KV_RAW, json.dumps(raw))
    mp = {no: classify(cats, tree, grp) for no, cats in raw.items()}
    store.kv_set(KV, json.dumps(mp, ensure_ascii=False))
    return mp


def category_of(mp: dict[str, str], dims: dict[str, Any]) -> str:
    return mp.get(str(dims.get("product_no", ""))) or dims.get("category") or "기타"
