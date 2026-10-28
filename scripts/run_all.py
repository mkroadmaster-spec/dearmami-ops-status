#!/usr/bin/env python
"""전 채널 수집 실행.

  python scripts/run_all.py --mode demo --days 30            # 데모 데이터로 틀 확인
  python scripts/run_all.py --mode live --date 2026-10-27    # 하루
  python scripts/run_all.py --mode live --days 14            # 최근 14일 백필 (어제까지, KST)
  python scripts/run_all.py --mode live --days 3 --skip competitor
  python scripts/run_all.py --reset --mode live --days 14    # demo → live 전환 시 기존 facts 비우고 수집
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cafe24_ops import config, pipeline  # noqa: E402
from cafe24_ops.clients import slack  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["live", "demo"], default=None, help="기본: CAFE24_OPS_MODE (live)")
    ap.add_argument("--date", default=None, help="수집 종료일 YYYY-MM-DD (기본: KST 어제)")
    ap.add_argument("--days", type=int, default=1, help="종료일 포함 최근 N일")
    ap.add_argument("--skip", default="", help="건너뛸 소스 콤마 구분 (cafe24,cafe24_analytics,ga4,ads,competitor)")
    ap.add_argument("--reset", action="store_true", help="실행 전 facts/kpi_daily 전체 삭제 (demo→live 전환)")
    ap.add_argument("--notify", action="store_true", help="실패 채널 있으면 Slack 알림")
    a = ap.parse_args()

    mode = a.mode or config.mode()
    if a.mode:
        os.environ["CAFE24_OPS_MODE"] = a.mode
    end = a.date or pipeline.yesterday()
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}

    store = Store()
    print(f"[run_all] mode={mode} db={'postgres' if store.is_pg else 'sqlite'} end={end} days={a.days} skip={sorted(skip) or '-'}")
    if a.reset:
        store.clear_all_facts()
        print("[run_all] facts/kpi_daily 초기화")

    results = pipeline.run_range(store, end, a.days, mode=mode, skip=skip)
    failed: set[str] = set()
    for r in results:
        parts = []
        for src, st in r["sources"].items():
            parts.append(f"{src}={st['status']}")
            if st["status"] in ("fail", "partial"):
                failed.add(src)
        k = r["kpi"]
        print(f"  {r['date']}  {' '.join(parts)}  | 매출 {k.get('gross_sales') or 0:,.0f} 주문 {k.get('orders') or 0:,.0f} 광고비 {k.get('ad_cost') or 0:,.0f}")
    for src, st in results[-1]["sources"].items():
        if st["status"] != "ok":
            print(f"  · {src}: {st['message']}")

    if failed:
        print(f"[run_all] ⚠ 수집 실패/부분 실패 채널: {', '.join(sorted(failed))}")
        if a.notify and slack.is_configured():
            slack.send(f"🔴 [{config.sources().get('brand')}] 수집 실패 채널: {', '.join(sorted(failed))} ({end})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
