"""DB 용량 정리 — 오래된 '상세' 행만 지운다. 기본은 미리보기(아무것도 지우지 않음).

무료 DB(0.5GB)가 차면 저장이 멈춘다. 일별 합계(kpi_daily)와 매출·광고 채널 합계는 남기고,
상품·검색어·키워드·소재처럼 줄 수가 많은 상세 데이터 중 오래된 것만 지운다.

  python scripts/prune.py                         # 미리보기: 소스별 줄 수, 기준일 이전 줄 수
  python scripts/prune.py --before 2025-07-01     # 그 날짜 이전 상세가 몇 줄인지
  python scripts/prune.py --before 2025-07-01 --sources cafe24_analytics,naver_keyword --apply   # 실제 삭제

지우면 되돌릴 수 없다(다시 수집해야 한다). 반드시 사용자에게 확인받고 --apply 를 붙인다.
지운 뒤 kpi_daily(카드·일별 그래프)는 그대로다. 사라지는 것은 그 기간의 상품별·검색어별·키워드별·소재별 화면.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.store import Store  # noqa: E402

DETAIL = ("cafe24_analytics", "naver_keyword", "naver_place", "creative", "google_creative", "kakao_creative", "ad_campaign", "ga4_channel", "ga4_page", "ga4_event")
KEEP_METRICS = {"cafe24_analytics": ("visit_count", "first_visit_count", "re_visit_count")}  # 방문 합계는 kpi 재계산에 필요 → 남긴다


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=(date.today() - timedelta(days=400)).isoformat(), help="이 날짜 이전 상세를 대상 (기본: 400일 전)")
    ap.add_argument("--sources", default=",".join(DETAIL))
    ap.add_argument("--apply", action="store_true", help="실제로 지운다 (없으면 미리보기)")
    a = ap.parse_args()
    store = Store()
    size = store.db_size_mb()
    total = store.rows("SELECT COUNT(*) AS n FROM facts")[0]["n"]
    print(f"DB 크기: {size:.0f}MB" if size is not None else "DB 크기: (SQLite)", f"· facts {total:,}줄 · 기준일 {a.before} 이전")
    freed = 0
    for src in [s.strip() for s in a.sources.split(",") if s.strip() in DETAIL]:
        keep = KEEP_METRICS.get(src, ())
        cond = "source=? AND date<?" + (f" AND metric NOT IN ({','.join('?' * len(keep))})" if keep else "")
        n = store.rows(f"SELECT COUNT(*) AS n FROM facts WHERE {cond}", (src, a.before, *keep))[0]["n"]
        alln = store.rows("SELECT COUNT(*) AS n FROM facts WHERE source=?", (src,))[0]["n"]
        print(f"  {src:<18} 전체 {alln:>9,}줄 · 대상 {n:>9,}줄 (약 {n * 0.42 / 1024:.0f}MB)")
        freed += n
        if a.apply and n:
            store.exec(f"DELETE FROM facts WHERE {cond}", (src, a.before, *keep))
    print(f"{'삭제함' if a.apply else '미리보기 — 지우려면 --apply'}: {freed:,}줄 (약 {freed * 0.42 / 1024:.0f}MB)")
    if a.apply and store.is_pg:
        print("참고: Postgres 는 지운 자리를 새 데이터가 재사용한다. 표시 용량은 바로 줄지 않을 수 있다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
