#!/usr/bin/env python
"""카페24 OAuth 토큰 최초 발급 헬퍼.

  1) python scripts/cafe24_auth.py --authorize [--redirect-uri https://localhost]
     → 출력된 URL 을 브라우저로 열고 '승인' → 주소창의 code= 값 복사 (⚠ 코드는 1분 만료)
  2) python scripts/cafe24_auth.py --code <코드> [--redirect-uri https://localhost] [--to-db]
     → access/refresh 토큰을 DB(app_kv)에 저장(기본) + secrets.env 에 넣을 줄 출력
  3) python scripts/cafe24_auth.py --status      # 저장된 토큰·scope 확인
  4) python scripts/cafe24_auth.py --reset       # DB 의 카페24 토큰 삭제(키 재발급 후)

redirect_uri 는 개발자센터 App관리 > Redirect URI(s) 와 글자까지 동일해야 한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cafe24_ops import config  # noqa: E402
from cafe24_ops.clients import cafe24_client as cc  # noqa: E402
from cafe24_ops.store import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--authorize", action="store_true")
    ap.add_argument("--code")
    ap.add_argument("--redirect-uri", default=None)
    ap.add_argument("--to-db", action="store_true", help="(기본 동작) DB 저장. 호환용 플래그")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()

    mall_id = config.sources()["shop"]["mall_id"]
    client_id, secret = config.env("CAFE24_CLIENT_ID"), config.env("CAFE24_CLIENT_SECRET")
    redirect = a.redirect_uri or config.env("CAFE24_REDIRECT_URI", "https://localhost")
    if not (mall_id and client_id and secret):
        print("❌ CAFE24_MALL_ID / CAFE24_CLIENT_ID / CAFE24_CLIENT_SECRET 를 config/secrets.env 에 먼저 채우세요")
        return 1

    store = Store()
    if a.reset:
        store.kv_delete(cc.KV_ACCESS, cc.KV_REFRESH, cc.KV_SCOPES, cc.KV_EXPIRES)
        print("✓ DB 의 카페24 토큰 삭제 완료 → --authorize 부터 다시")
        return 0
    if a.status:
        acc, ref, sc = store.kv_get(cc.KV_ACCESS), store.kv_get(cc.KV_REFRESH), store.kv_get(cc.KV_SCOPES)
        print(f"access: {'있음' if acc else '없음'}  refresh: {'있음' if ref else '없음'}")
        print(f"scopes: {sc or '(기록 없음)'}")
        miss = cc.missing_scopes(sc) if sc else cc.SCOPES
        if miss:
            print(f"⚠ 누락 scope: {', '.join(miss)} → 개발자센터 앱 권한 7개 전부 체크 후 재인증")
        return 0
    if a.authorize:
        print("아래 URL 을 브라우저로 열어 승인하세요 (1분 내 다음 단계 실행):\n")
        print(cc.authorize_url(mall_id, client_id, redirect))
        print(f"\n승인 후 주소창 `{redirect}?code=XXXX&state=ops` 의 XXXX 를 복사 →")
        print("python scripts/cafe24_auth.py --code XXXX" + (f" --redirect-uri {redirect}" if a.redirect_uri else ""))
        return 0
    if a.code:
        tok = cc.exchange_code(mall_id, client_id, secret, a.code.strip(), redirect)
        cc.save_tokens(store, tok)
        granted = tok.get("scopes") or tok.get("scope") or ""
        if isinstance(granted, list):
            granted = ",".join(granted)
        print("✓ 토큰 발급 + DB(app_kv) 저장 완료")
        print(f"  부여 scope: {granted}")
        miss = cc.missing_scopes(str(granted))
        if miss:
            print(f"  ⚠ 누락 scope: {', '.join(miss)} — 해당 지표가 오류 없이 빈 값으로 보입니다. 앱 권한 7개 체크 후 재인증 권장")
        print("\n(선택) secrets.env / GitHub Secrets 에 넣을 값 — DB 에 저장됐으므로 필수는 아님:")
        print(f"CAFE24_ACCESS_TOKEN={tok.get('access_token')}")
        print(f"CAFE24_REFRESH_TOKEN={tok.get('refresh_token')}")
        print("\n다음: python scripts/smoke_live.py --check")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
