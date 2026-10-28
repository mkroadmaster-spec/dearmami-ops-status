#!/usr/bin/env python
"""주간(또는 월간) 리포트 .docx 를 파일로 생성 — CI 아티팩트용.

  python scripts/weekly_report.py                 # 지난주 → dist/reports/weekly-report-<월요일>.docx
  python scripts/weekly_report.py --week 2026-10-20
  python scripts/weekly_report.py --monthly [--month 2026-09]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cafe24_ops import report_docx  # noqa: E402
from cafe24_ops.etl import period_report  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=None)
    ap.add_argument("--monthly", action="store_true")
    ap.add_argument("--month", default=None)
    a = ap.parse_args()
    store = Store()
    data = period_report.monthly_report(store, a.month) if a.monthly else period_report.weekly_report(store, a.week)
    out_dir = ROOT / "dist" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"monthly-report-{data['range']['from'][:7]}.docx" if a.monthly else f"weekly-report-{data['range']['from']}.docx"
    (out_dir / name).write_bytes(report_docx.build(data))
    print(f"✓ {out_dir / name}")
    print(f"  {data['title']} · {data['headline']}")
    if data["missing_dates"]:
        print(f"  ⚠ missing_dates: {', '.join(data['missing_dates'])}")
    if data["empty"]:
        print("  ⚠ 이 기간에 수집된 날짜가 없음 — 리포트는 빈 채로 렌더됨")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
