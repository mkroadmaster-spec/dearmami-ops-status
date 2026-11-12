"""카카오모먼트 소재 구조 진단 — 소재 단위 리포트·소재 목록/상세의 응답 모양 (금액 값은 출력하지 않음)."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cafe24_ops.clients.ads_kakao import KakaoMomentClient  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402

k = KakaoMomentClient(Store())
d = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
d7 = (date.today() - timedelta(days=7)).strftime("%Y%m%d")


def show(title, path, params, n=2):
    print(f"\n===== {title} {path} {params} =====")
    r = k._get(path, params)
    print("status", r.status_code)
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        print(r.text[:300]); return None
    if isinstance(j, dict):
        print("keys:", list(j.keys()))
        rows = j.get("data") or j.get("content") or []
    else:
        rows = j
    print("rows:", len(rows) if isinstance(rows, list) else type(rows).__name__)
    for x in (rows[:n] if isinstance(rows, list) else [rows]):
        print("  ", json.dumps(x, ensure_ascii=False)[:700])
    return rows


rep = show("소재 단위 리포트(하루)", "/adAccounts/report", {"level": "CREATIVE", "start": d, "end": d, "metricsGroup": "BASIC,PIXEL_SDK_CONVERSION"})
show("소재 단위 리포트(7일 · 일자 구분?)", "/adAccounts/report", {"level": "CREATIVE", "start": d7, "end": d, "metricsGroup": "BASIC", "timeUnit": "DAY"}, 3)
camps = show("캠페인 목록", "/campaigns", {}, 1) or []
cid = camps[0].get("id") if camps and isinstance(camps[0], dict) else None
if cid:
    groups = show("광고그룹 목록", "/adGroups", {"campaignId": cid}, 1) or []
    gid = groups[0].get("id") if groups and isinstance(groups[0], dict) else None
    if gid:
        crs = show("소재 목록", "/creatives", {"adGroupId": gid}, 1) or []
        crid = crs[0].get("id") if crs and isinstance(crs[0], dict) else None
        if crid:
            show("소재 상세", f"/creatives/{crid}", {}, 1)
