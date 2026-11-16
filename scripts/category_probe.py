"""카테고리 구조 진단 — 카테고리 트리(이름·depth)와 상품별 카테고리 소속 모양. 금액 출력 없음."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.clients import cafe24_client as cc  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402

c = cc.Cafe24Client.from_store(Store())
cats, off = [], 0
while True:
    ch = c.get("/admin/categories", {"limit": 100, "offset": off}).get("categories", [])
    cats += ch
    if len(ch) < 100:
        break
    off += 100
print("categories:", len(cats), "| keys:", sorted(cats[0].keys()) if cats else None)
for x in [x for x in cats if x.get("category_depth") == 1 or x.get("use_display") == "T"][80 if len(sys.argv) > 1 else 0:]:
    print(f"  #{x.get('category_no')} d{x.get('category_depth')} parent={x.get('parent_category_no')} display={x.get('display_type')} use={x.get('use_display')} :: {json.dumps(x.get('full_category_name'), ensure_ascii=False)}")
ps = c.products(limit=100, offset=0, fields="product_no,product_name,category,display,selling")
print("\nproducts sample:", len(ps), "| keys:", sorted(ps[0].keys()) if ps else None)
for p in ps[:8]:
    print("  ", p.get("product_no"), p.get("product_name"), json.dumps(p.get("category"), ensure_ascii=False)[:300])
print("categories per product:", Counter(len(p.get("category") or []) for p in ps))

for no in sys.argv[1:]:
    r = c.get(f"/admin/categories/{no}/products", {"display_group": 1, "limit": 5})
    print(f"\n/categories/{no}/products keys:", list(r.keys()), json.dumps(r, ensure_ascii=False)[:400])
    try:
        print("  count:", c.get(f"/admin/categories/{no}/products/count", {"display_group": 1}))
    except Exception as e:  # noqa: BLE001
        print("  count ERR", str(e)[:200])
p1 = c.get("/admin/products/33529", {})
print("\nproduct detail category:", json.dumps((p1.get("product") or {}).get("category"), ensure_ascii=False)[:300])
