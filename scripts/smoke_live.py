#!/usr/bin/env python
"""채널별 자격증명 확인 — 설정된 채널만 실제 API 를 1회 호출해 인증을 검증한다.

  python scripts/smoke_live.py --check
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cafe24_ops import config  # noqa: E402
from cafe24_ops.clients import (ads_google, ads_kakao, ads_meta, ads_naver, cafe24_client as cc,  # noqa: E402
                                ga4, naver_datalab, slack, telegram)
from cafe24_ops.clients.cafe24_analytics import Cafe24Analytics  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402


def main() -> int:
    store = Store()
    d = (date.today() - timedelta(days=1)).isoformat()
    ok = True

    def report(name: str, fn):
        nonlocal ok
        try:
            print(f"  ✓ {name}: {fn()}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"  ✗ {name}: {type(e).__name__}: {str(e)[:200]}")

    print(f"[smoke] mode={config.mode()} db={'postgres' if store.is_pg else 'sqlite'} date={d}\n")

    if cc.is_configured():
        def _c24():
            c = cc.Cafe24Client.from_store(store)
            return f"orders/count={c.orders_count(d, d)}"
        report("카페24 Admin API", _c24)
        def _an():
            c = cc.Cafe24Client.from_store(store)
            v = Cafe24Analytics(c).visitors_view(d)
            return f"visitors/view visit_count={v['visit_count']:.0f}"
        report("카페24 통계 API (read_analytics)", _an)
    else:
        print("  - 카페24: 미설정 (STEP 1)")

    if ga4.is_configured():
        report("GA4", lambda: f"visitors={ga4.GA4Client().site_daily(d)['visitors']:.0f}")
    else:
        print("  - GA4: 미설정 (STEP 2)")

    if ads_meta.is_configured():
        report("Meta 광고", lambda: f"spend={ads_meta.MetaAdsClient(store).account_insights(d)['ad_cost']:.0f}")
    else:
        print("  - Meta: 미설정 (STEP 3)")
    if ads_naver.is_configured():
        report("네이버 검색광고", lambda: f"campaigns={len(ads_naver.NaverSAClient().campaigns())}")
    else:
        print("  - 네이버SA: 미설정 (STEP 4)")
    if naver_datalab.is_configured():
        brands = [str(b) for b in config.sources().get("competitors") or []][:1] or ["테스트"]
        report("네이버 데이터랩", lambda: f"groups={len(naver_datalab.NaverDataLab().trend(brands, d, d))}")
    else:
        print("  - 네이버 오픈API: 미설정 (STEP 5)")
    if ads_kakao.is_configured():
        report("카카오모먼트", lambda: f"cost={ads_kakao.KakaoMomentClient().account_report(d)['ad_cost']:.0f}")
    else:
        print("  - 카카오: 미설정 (STEP 6)")
    if ads_google.is_configured():
        report("Google Ads", lambda: f"cost={ads_google.GoogleAdsClient().daily(d)['ad_cost']:.0f}")
    else:
        print("  - Google Ads: 미설정 (STEP 7)")
    if slack.is_configured():
        report("Slack", lambda: f"sent={slack.send('✅ cafe24-ops-status smoke test')}")
    else:
        print("  - Slack: 미설정 (STEP 8, 선택)")
    if telegram.is_configured():
        report("텔레그램", lambda: f"sent={telegram.send('✅ cafe24-ops-status 연결 테스트 — 이 메시지가 보이면 알림 연결 완료')}")
    else:
        print("  - 텔레그램: 미설정 (STEP 8)")

    print("\n[smoke]", "모두 정상" if ok else "실패 항목 있음 — 메시지를 그대로 붙여 문의")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
