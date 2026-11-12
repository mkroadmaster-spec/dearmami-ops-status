"""카페24 통계 API 진단 — 각 경로의 실제 응답 모양(키·첫 행)과 DB 에 쌓인 지표 합계를 로그에 출력.

필드명이 추측과 달라 0 으로 저장되는 블록을 찾기 위한 도구. (python scripts/analytics_probe.py [YYYY-MM-DD])
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.clients import cafe24_client as cc  # noqa: E402
from cafe24_ops.clients.cafe24_analytics import Cafe24Analytics  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402

PATHS = ("/visitors/view", "/carts/action", "/products/sales", "/products/view", "/visitpaths/keywords",
         "/visitpaths/domains", "/visitpaths/ads", "/pages/view", "/members/sales")


def main() -> None:
    d = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).isoformat()
    store = Store()
    an = Cafe24Analytics(cc.Cafe24Client.from_store(store))
    for p in PATHS:
        print(f"\n===== {p} {d} =====")
        try:
            data = an.get(p, d, d)
        except Exception as e:  # noqa: BLE001
            print("ERROR", e)
            continue
        print("top keys:", {k: (type(v).__name__, len(v) if isinstance(v, (list, dict)) else v) for k, v in data.items()})
        for k, v in data.items():
            if isinstance(v, list):
                print(f"[{k}] rows={len(v)}")
                for row in v[:2]:
                    print("  ", json.dumps(row, ensure_ascii=False)[:600])
    print("\n===== DB cafe24_analytics 지표 (최근 7일 합계 · 행수) =====")
    start = (date.fromisoformat(d) - timedelta(days=6)).isoformat()
    rows = store.rows("SELECT metric, COUNT(*) AS n, SUM(value) AS s FROM facts WHERE source=? AND date>=? AND date<=? "
                          "GROUP BY metric ORDER BY metric", ("cafe24_analytics", start, d))
    for r in rows:
        print(f"  {r['metric']:<22} rows={r['n']:<6} sum={r['s']}")
    print("\n===== kpi_daily 최근 7일 metric 목록 =====")
    for r in store.rows("SELECT metric, SUM(value) AS s FROM kpi_daily WHERE date>=? AND date<=? GROUP BY metric ORDER BY metric",
                            (start, d)):
        print(f"  {r['metric']:<28} sum={r['s']}")


if __name__ == "__main__":
    main()
