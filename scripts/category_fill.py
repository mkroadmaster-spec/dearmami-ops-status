"""과거 매출 상품 전체의 카테고리 매핑 채우기 (1회). 이후엔 매일 수집 때 새 상품만 자동 추가.

python scripts/category_fill.py               → 아직 매핑이 없는 상품만 채움
python scripts/category_fill.py --reclassify  → config/metrics.yaml 의 category_groups 를 고친 뒤 전체 상품을 다시 분류
                                                 (이미 '기타'로 저장된 상품은 이 옵션이 있어야 바뀐다)
출력은 상품 수·카테고리별 상품 수만 (금액 없음).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.clients import cafe24_client as cc  # noqa: E402
from cafe24_ops.etl import category_map  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402

store = Store()
nos = {r["n"] for r in store.rows(
    "SELECT DISTINCT dims AS n FROM facts WHERE source='cafe24' AND metric='product_sales'")}
import json  # noqa: E402
pnos = set()
for d in nos:
    try:
        pnos.add(str((json.loads(d) if isinstance(d, str) else d).get("product_no", "")))
    except Exception:  # noqa: BLE001
        pass
pnos.discard("")
print("판매된 상품 수:", len(pnos), "| 기존 매핑:", len(category_map.load(store)), flush=True)
client = cc.Cafe24Client.from_store(store)
mp = category_map.ensure(store, client, pnos)
if "--reclassify" in sys.argv:
    mp = category_map.reclassify(store, client)
    print("전체 재분류 완료")
print("매핑 완료:", len(mp))
print("카테고리별 상품 수:", dict(Counter(mp[n] for n in pnos if n in mp).most_common()))
