#!/usr/bin/env python
"""대시보드를 서버 없이 열 수 있는 정적 HTML 로 내보내기 (API 응답 스냅샷 + Chart.js 내장).

  python scripts/export_static.py                 # dist/index.html (GitHub Pages 등 어디서나 열림)
  python scripts/export_static.py --artifact      # dist/dashboard-static.html (문서 스켈레톤 없이 본문만 — Artifact 게시용)

프리셋 7/14/30일(최신일 기준) + 기본 주간/월간 리포트 스냅샷을 담는다. 사용자 지정 기간·리포트 이동·docx 는 정적 모드에서 비활성.
실데이터 연결 후에도 같은 명령으로 재생성하면 된다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

PRESETS = (1, 7, 14, 30)
CMPS = ("prev", "week", "month", "year")


def _add_months(d: _date, n: int) -> _date:
    y, m = d.year, d.month + n
    while m < 1:
        m += 12; y -= 1
    while m > 12:
        m -= 12; y += 1
    import calendar
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def _cmp_range(f: _date, t: _date, mode: str) -> tuple[_date, _date]:
    n = (t - f).days + 1
    if mode == "week":
        return f - timedelta(days=7), t - timedelta(days=7)
    if mode == "month":
        return _add_months(f, -1), _add_months(t, -1)
    if mode == "year":
        return _add_months(f, -12), _add_months(t, -12)
    return f - timedelta(days=n), f - timedelta(days=1)


def build_snapshot() -> dict:
    c = TestClient(app)

    def get(p: str):
        r = c.get(p)
        r.raise_for_status()
        return r.json()

    dates = get("/api/dates")
    if not dates.get("max"):
        raise SystemExit("수집 데이터가 없습니다 → python scripts/run_all.py --mode demo --days 60")
    to = _date.fromisoformat(dates["max"])
    snap = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": get("/api/config"), "dates": dates, "channels": get("/api/channels"),
        "logs": get("/api/logs?limit=50"), "digest": get(f"/api/digest?date={dates['max']}"),
        "period_comparison": get(f"/api/period-comparison?date={dates['max']}"),
        "report_weekly": get("/api/report/weekly"), "report_monthly": get("/api/report/monthly"),
        "competitor_directory": get("/api/competitors/directory"), "ranges": {},
    }
    for n in PRESETS:
      for mode in CMPS:
        f = to - timedelta(days=n - 1)
        cf, ct = _cmp_range(f, to, mode)
        q = f"from={f.isoformat()}&to={to.isoformat()}&cmp_from={cf.isoformat()}&cmp_to={ct.isoformat()}"
        snap["ranges"][f"{n}|{mode}"] = {
            "summary": get(f"/api/summary?{q}"), "daily": get(f"/api/daily?{q}"), "breakdown": get(f"/api/breakdown?{q}"),
            "shop": get(f"/api/shop/analytics?{q}"), "ads": get(f"/api/ads/channels?{q}"),
            "keywords": get(f"/api/ads/keywords?{q}&channel=naver_powerlink"), "place": get(f"/api/ads/keywords?{q}&channel=naver_place"),
            "creatives": get(f"/api/creatives/overview?{q}"), "creative_trend": get(f"/api/creatives/trend?{q}"),
            "ga4": get(f"/api/ga4/site?{q}"), "competitors": get(f"/api/competitors/trend?{q}"),
        }
    return snap


def render(snap: dict, artifact: bool) -> str:
    html = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    chart = (ROOT / "dashboard" / "vendor" / "chart.umd.js").read_text(encoding="utf-8")
    data = json.dumps(snap, ensure_ascii=False).replace("</", "<\\/")
    inject = f"<script>\n{chart}\n</script>\n<script>window.__SNAPSHOT__ = {data};</script>"
    html = html.replace('<script src="/static/vendor/chart.umd.js"></script>', inject, 1)
    brand = snap["config"].get("brand") or ""
    if brand:  # 게시/갤러리 제목에 업체명
        html = html.replace("<title>운영현황 대시보드</title>", f"<title>{brand} 운영현황</title>", 1)
    if artifact:  # 게시 시 스켈레톤이 감싸므로 <title>/<meta>/<style> + body 내용만 남긴다
        head = re.search(r"<head>(.*?)</head>", html, re.S).group(1)
        body = re.search(r"<body>(.*?)</body>", html, re.S).group(1)
        head = re.sub(r'<meta charset="utf-8">\s*|<meta name="viewport"[^>]*>\s*', "", head)
        html = head.strip() + "\n" + body.strip() + "\n"
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    snap = build_snapshot()
    out = Path(a.out) if a.out else ROOT / "dist" / ("dashboard-static.html" if a.artifact else "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(snap, a.artifact), encoding="utf-8")
    print(f"✓ {out} ({out.stat().st_size // 1024} KB) · 기준일 {snap['dates']['max']} · 모드 {snap['config']['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
