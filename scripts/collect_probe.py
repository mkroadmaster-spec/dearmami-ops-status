"""수집기 시간 측정 — 지정 수집기를 날짜별로 실행(DB 저장 안 함)해 소요 시간·건수만 출력. 금액은 출력하지 않음 (공개 로그).

python scripts/collect_probe.py naver_keyword,kakao_creative 2025-01-01 2025-01-02 2026-10-01
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.collectors import REGISTRY  # noqa: E402
from cafe24_ops.collectors.base import PartialFailure  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402

names = set(sys.argv[1].split(","))
store = Store()
for d in sys.argv[2:]:
    for c in REGISTRY:
        if c.name not in names:
            continue
        t0 = time.time()
        try:
            facts = c.collect(store, d)
            st = "ok"
        except PartialFailure as pf:
            facts, st = pf.facts, f"partial: {str(pf)[:300]}"
        except Exception as e:  # noqa: BLE001
            facts, st = [], f"fail {type(e).__name__}: {str(e)[:300]}"
        ids = {f["dims"].get("ad_id") or f["dims"].get("keyword_id") for f in facts}
        print(f"{d} {c.name:<15} {time.time() - t0:6.1f}s  facts={len(facts)} entities={len(ids)}  {st}", flush=True)
