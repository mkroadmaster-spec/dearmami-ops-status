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
    print("\n===== limit/offset 지원 여부 (/visitpaths/domains) =====")
    for extra in ({"limit": 1000}, {"limit": 500}, {"limit": 100, "offset": 100}):
        try:
            data = an.get("/visitpaths/domains", d, d, **extra)
            print(extra, "rows=", len(next((v for v in data.values() if isinstance(v, list)), [])))
        except Exception as e:  # noqa: BLE001
            print(extra, "ERROR", str(e)[:200])
    print("\n===== 신규가입 수 후보 (Admin API) =====")
    print("granted scopes:", store.kv_get("cafe24_token_scopes"))
    c = an.c
    for path, params in (("/admin/customersprivacy/count", {"created_start_date": d, "created_end_date": d}),
                         ("/admin/customers/count", {"created_start_date": d, "created_end_date": d}),
                         ("/admin/customersprivacy", {"created_start_date": d, "created_end_date": d, "limit": 1, "fields": "member_id,created_date"})):
        try:
            r = c._get_retry(f"{cc.base_url(c.mall_id)}{path}", params)
            print(path, r.status_code, r.text[:300].replace(c.mall_id, "<mall>"))
        except Exception as e:  # noqa: BLE001
            print(path, "ERROR", str(e)[:200])
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


def db_size() -> None:
    s = Store()
    if s.is_pg:
        r = s.rows("SELECT pg_size_pretty(pg_database_size(current_database())) AS size")
        print("DB size:", r[0]["size"])
    for r in s.rows("SELECT source, COUNT(*) AS n FROM facts GROUP BY source ORDER BY n DESC"):
        print(f"  facts {r['source']:<20} {r['n']:>10,}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "size":
        db_size()
    else:
        main()
