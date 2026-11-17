"""광고 데이터 누락 점검 — 채널별로 행이 없는 날, 광고비 0 인 날, 평소 대비 급감한 날을 날짜 구간으로 출력.

금액은 출력하지 않는다 (공개 로그) — 날짜와 '평소 대비 %' 만.
python scripts/ads_gap_probe.py [시작일 YYYY-MM-DD]   (기본 2025-01-01)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.pipeline import yesterday  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402

start = date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2025-01-01")
end = date.fromisoformat(yesterday())
store = Store()


def ranges(days: list[str]) -> str:
    """연속 날짜를 구간으로 묶는다."""
    if not days:
        return "없음"
    out, a, b = [], days[0], days[0]
    for d in days[1:]:
        if date.fromisoformat(d) - date.fromisoformat(b) == timedelta(days=1):
            b = d
        else:
            out.append((a, b)); a = b = d
    out.append((a, b))
    return ", ".join(x if x == y else f"{x}~{y}({(date.fromisoformat(y) - date.fromisoformat(x)).days + 1}일)" for x, y in out)


cost: dict[str, dict[str, float]] = defaultdict(dict)
imp: dict[str, dict[str, float]] = defaultdict(dict)
for r in store.rows("SELECT date, metric, dims, value FROM facts WHERE source='ads' AND metric IN ('ad_cost','impressions') AND date>=? AND date<=?",
                    (start.isoformat(), end.isoformat())):
    ch = json.loads(r["dims"] or "{}").get("channel", "?")
    (cost if r["metric"] == "ad_cost" else imp)[ch][r["date"]] = float(r["value"] or 0)

print(f"점검 기간 {start} ~ {end}")
for ch in sorted(cost):
    c = cost[ch]
    first, last = min(c), max(c)
    span = [(date.fromisoformat(first) + timedelta(days=i)).isoformat() for i in range((end - date.fromisoformat(first)).days + 1)]
    no_row = [d for d in span if d not in c]
    zero = [d for d in span if d in c and c[d] == 0 and imp[ch].get(d, 0) == 0]
    low = []
    for i, d in enumerate(span):
        if c.get(d, 0) <= 0:
            continue
        base = [c[x] for x in span[max(0, i - 14):i] if c.get(x, 0) > 0]
        if len(base) >= 7 and c[d] < median(base) * 0.3:
            low.append(f"{d}({c[d] / median(base) * 100:.0f}%)")
    print(f"\n[{ch}] 첫 데이터 {first} · 마지막 {last} · 보유 {len(c)}일 / 기대 {len(span)}일")
    print(f"  행 없음 {len(no_row)}일: {ranges(no_row)}")
    print(f"  광고비·노출 모두 0 {len(zero)}일: {ranges(zero)}")
    print(f"  평소(직전 14일 중위)의 30% 미만 {len(low)}일: {', '.join(low[-25:]) or '없음'}")

print("\n[최근 21일 채널별 상태]  O=광고비 있음 · 0=0원 · -=행 없음")
days = [(end - timedelta(days=i)).isoformat() for i in range(20, -1, -1)]
print("  " + " " * 18 + " ".join(d[8:] for d in days))
for ch in sorted(cost):
    print(f"  {ch:<18}" + "  ".join("O" if cost[ch].get(d, 0) > 0 else ("0" if d in cost[ch] else "-") for d in days))

print("\n[최근 30일 수집 로그 중 ads·소재·키워드의 실패/부분실패]")
since = (end - timedelta(days=30)).isoformat()
rows = store.rows("SELECT run_at, date, source, status, message FROM collect_log WHERE date>=? AND status IN ('fail','partial') "
                  "AND source IN ('ads','creative','google_creative','kakao_creative','naver_keyword') ORDER BY run_at DESC LIMIT 40", (since,))
for r in rows:
    print(f"  {r['run_at'][:16]} {r['date']} {r['source']:<15} {r['status']:<7} {(r['message'] or '')[:260]}")
if not rows:
    print("  없음")
