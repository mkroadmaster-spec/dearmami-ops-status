"""크리테오 연결 진단 — DB 없이 동작. 토큰 발급 → 접근 가능한 광고주 → 일별 리포트 응답 모양.

금액·수치는 출력하지 않는다 (공개 로그) — 값이 있는지와 열 이름만.
python scripts/criteo_probe.py [YYYY-MM-DD]
"""
from __future__ import annotations

import csv
import io
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.clients import ads_criteo as ac  # noqa: E402

d = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).isoformat()
print("is_configured:", ac.is_configured())
try:
    c = ac.CriteoClient()
except Exception as e:  # noqa: BLE001
    print("❌ 토큰 발급 실패:", str(e)[:300]); raise SystemExit(1)
print("✅ 토큰 발급 성공")
h = {"Authorization": f"Bearer {c.token}", "Accept": "application/json"}

# 접근 가능한 광고주 (동의 화면에서 승인된 것)
for ver in ac.VERSIONS:
    r = requests.get(f"{ac.HOST}/{ver}/advertisers/me", headers=h, timeout=30)
    if r.status_code in (404, 410):
        continue
    print(f"advertisers/me [{ver}] status {r.status_code}")
    if r.status_code == 200:
        data = r.json().get("data", [])
        print("  승인된 광고주 수:", len(data))
        for a in data[:5]:
            print("   - id", a.get("id"), "| name:", (a.get("attributes") or {}).get("advertiserName"))
    else:
        print("  ", r.text[:300])
    break

# 일별 리포트 — 최근 7일, 응답 열 이름과 행 수만
start = (date.fromisoformat(d) - timedelta(days=6)).isoformat()
body = {"startDate": f"{start}T00:00:00Z", "endDate": f"{d}T00:00:00Z", "timezone": "Asia/Seoul", "currency": "KRW",
        "dimensions": ["Day"], "format": "csv",
        "metrics": ["Displays", "Clicks", "AdvertiserCost", "SalesAllPc30d", "RevenueGeneratedAllPc30d"]}
if c.advertiser_id:
    body["advertiserIds"] = c.advertiser_id
for ver in ac.VERSIONS:
    r = requests.post(f"{ac.HOST}/{ver}/statistics/report", json=body, headers={"Authorization": f"Bearer {c.token}", "Accept": "text/csv"}, timeout=60)
    if r.status_code in (404, 410):
        print(f"report [{ver}] {r.status_code} → 다음 버전"); continue
    print(f"report [{ver}] status {r.status_code} · content-type {r.headers.get('content-type')}")
    if r.status_code >= 400:
        print("  ", r.text[:500]); break
    text = r.text.lstrip("﻿")
    first = text.split("\n", 1)[0]
    print("  첫 줄(열 이름):", first[:300])
    for delim in (",", ";", "\t"):
        rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
        if rows and len(rows[0]) > 1:
            print(f"  구분자 {delim!r} · 행 {len(rows)} · 열 {list(rows[0].keys())}")
            for k in ("Displays", "Clicks", "AdvertiserCost", "SalesAllPc30d", "RevenueGeneratedAllPc30d"):
                vals = [x.get(k) for x in rows]
                print(f"    {k:<26} 있음={sum(1 for v in vals if v not in (None, '', '0', '0.0'))}/{len(rows)}  예시 형식={'숫자' if vals and str(vals[0]).replace('.', '', 1).replace('-', '', 1).isdigit() else repr(str(vals[0])[:1]) + '…'}")
            print("  날짜 열 예시:", {k: rows[0][k] for k in rows[0] if k.lower() in ('day', 'date')})
            break
    break
# 수집기와 같은 방식으로 하루치 (값 유무만)
try:
    rep = c.daily(d)
    print(f"✅ daily({d}) 성공:", {k: ("있음" if v else "0") for k, v in rep.items()})
except Exception as e:  # noqa: BLE001
    print("❌ daily 실패:", str(e)[:400])
