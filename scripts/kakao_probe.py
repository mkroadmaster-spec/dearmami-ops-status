"""카카오모먼트 소재 진단 — 켜진 캠페인/광고그룹/소재 수, 소재 리포트 행 구조(소재별 분리 여부)."""
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
J = lambda r: r.json().get("content", []) if r.status_code == 200 else (print("ERR", r.status_code, r.text[:300]) or [])

camps = J(k._get("/campaigns", {}))
on = [c for c in camps if c.get("config") == "ON"]
print("campaigns:", len(camps), "ON:", len(on))
ids, fmts = [], []
for c in on[:6]:
    for g in J(k._get("/adGroups", {"campaignId": c["id"]})):
        if g.get("config") != "ON":
            continue
        crs = [x for x in J(k._get("/creatives", {"adGroupId": g["id"]})) if x.get("config") == "ON"]
        ids += [x["id"] for x in crs]
print("active creatives sampled:", len(ids))
if ids:
    det = k._get(f"/creatives/{ids[0]}", {}).json()
    print("format:", det.get("format"), "| image:", json.dumps(det.get("image"), ensure_ascii=False)[:200], "| thumb:", json.dumps(det.get("thumbnailImage"), ensure_ascii=False)[:200])
    for ex in ({}, {"dimension": "CREATIVE"}):
        r = k._get("/creatives/report", {"creativeId": ",".join(map(str, ids[:20])), "start": d7, "end": d, "metricsGroup": "BASIC,PIXEL_SDK_CONVERSION", **ex})
        print(f"\n== creatives/report {ex} status {r.status_code}")
        j = r.json()
        rows = j.get("data", []) if isinstance(j, dict) else []
        print("rows:", len(rows), "| err:" if r.status_code >= 400 else "", json.dumps(j, ensure_ascii=False)[:300] if r.status_code >= 400 else "")
        for x in rows[:3]:
            m = x.get("metrics", {})
            print("  ", json.dumps({**x, "metrics": sorted(m.keys())}, ensure_ascii=False)[:500])
