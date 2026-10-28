#!/usr/bin/env python
"""새 업체로 전환 — 업체별 값을 한 번에 교체하고 온보딩 기록(docs/clients/<id>.md)을 만든다.

  python scripts/new_client.py --id dearmami --brand 디어마미 --site https://dearmami.co.kr \
      --mall-id <카페24몰아이디> --competitors "경쟁사A,경쟁사B" \
      --categories "원피스:원피스,롱원피스;팬츠:팬츠,슬랙스;기타:"
  python scripts/new_client.py --id acme --brand 에이크미 --platform none     # 자사몰 없는 업체(광고만)

바꾸는 곳: config/sources.yaml · config/metrics.yaml(category_groups, --categories 줄 때만) · render.yaml(services[].name)
  · docs/clients/<id>.md(담당자 발급 체크리스트). 자격증명(secrets.env/GitHub Secrets)은 건드리지 않는다.
권장: 업체당 저장소 1개 — 이 저장소를 복제한 뒤 이 스크립트를 실행.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOURCES_TMPL = """# 업체별로 바꾸는 값 — scripts/new_client.py 가 이 파일을 다시 쓴다 (docs/NEW-CLIENT-CHECKLIST.md §2)
client_id: {client_id}
brand: "{brand}"
site_url: {site}
timezone: Asia/Seoul

shop:
  platform: {platform}            # cafe24 | none (자사몰 없으면 none → 카페24 수집기 자동 스킵)
  mall_id: "{mall_id}"            # 카페24 몰 아이디 (https://<여기>.cafe24.com). 비우면 환경변수 CAFE24_MALL_ID
  api_version: "2025-06-01"

ads:                          # 자격증명 없는 채널은 자동 스킵
  - channel: meta
    account_id: ""
  - channel: naver_sa
    customer_id: ""
  - channel: kakao
    account_id: ""
  - channel: google
    customer_id: ""

lead_gen: false               # true = 리드젠(상담·문의형): 전환=결과, CPA/CVR 중심

competitors:                  # name=데이터랩 키워드(최대 5), url/insta/domain/fb_query=경쟁사 모니터링 딥링크
{competitors}
"""

CLIENT_DOC = """# {brand} ({client_id}) — 온보딩 기록

생성일: {today} · 사이트: {site} · 플랫폼: {platform} · 몰 아이디: `{mall_id}`

## 0. 업체와 합의할 것
- [ ] 쇼핑몰 플랫폼이 카페24인지 (어드민 주소 `https://<몰아이디>.cafe24.com`) → `config/sources.yaml` `shop.mall_id`
- [ ] 덩어리: A 운영현황 / B 광고 / C SNS 중 무엇을 쓸지
- [ ] 실제 집행 중인 광고 채널 (없는 채널은 자격증명 없이 두면 자동 스킵)
- [ ] 카테고리명 (카페24 상품 카테고리 그대로) → `config/metrics.yaml` `category_groups`
- [ ] 경쟁사 브랜드명 최대 5개 → `config/sources.yaml` `competitors`
- [ ] 담당자 1명 (각 플랫폼 로그인·권한 보유자)

## 1. 담당자가 발급할 것 (docs/SETUP-GUIDE.md 순서)
| STEP | 항목 | 어디서 | 받을 값 | 상태 |
|---|---|---|---|---|
| 1 | 카페24 앱 | developers.cafe24.com → 앱 생성 → **scope 7개 전부** → Redirect URI `https://localhost` | Client ID / Secret / 몰 아이디 | [ ] |
| 1 | 카페24 토큰 | `scripts/cafe24_auth.py --authorize` → 승인(1분 내) → `--code` | DB 자동 저장 | [ ] |
| 2 | GA4 | GCP 서비스계정 JSON + GA4 속성 뷰어 + Data API 사용설정 | 속성 ID, JSON | [ ] |
| 3 | Meta | business.facebook.com 시스템 사용자 토큰(만료 없음, ads_read) | 토큰, 광고계정 ID | [ ] |
| 4 | 네이버 검색광고 | searchad.naver.com → API 사용 관리 | API_KEY, SECRET_KEY, CUSTOMER_ID | [ ] |
| 5 | 네이버 오픈API | developers.naver.com → 데이터랩 | Client ID / Secret | [ ] |
| 6 | 카카오모먼트 | developers.kakao.com + moment.kakao.com | 토큰, 광고계정 ID | [ ] |
| 7 | Google Ads | API 센터 개발자 토큰 + OAuth | 4종 | [ ] |
| 8 | Slack | Incoming Webhook | URL | [ ] |
| 9 | Neon / GitHub / Render | DATABASE_URL, Secrets, Blueprint | 배포 URL | [ ] |

## 2. 진행 로그
- {today}: `new_client.py` 로 설정 생성. 데모 모드로 틀 확인.

## 3. 업체 특이사항
- (예: 리드젠이면 전환=결과, 크리테오 집행 중이면 광고비 누락 고지 등)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="영문 식별자 (폴더/서비스명)")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--site", default="")
    ap.add_argument("--platform", default="cafe24", choices=["cafe24", "none"])
    ap.add_argument("--mall-id", default="")
    ap.add_argument("--competitors", default="", help="콤마 구분")
    ap.add_argument("--categories", default="", help="'그룹:이름1,이름2;그룹2:이름3' (생략 시 metrics.yaml 유지)")
    ap.add_argument("--service-name", default=None, help="Render 서비스명 (기본 <id>-ops-dashboard)")
    a = ap.parse_args()

    cid = re.sub(r"[^a-z0-9-]", "-", a.id.lower())
    comps = [c.strip() for c in a.competitors.split(",") if c.strip()] or [a.brand]
    (ROOT / "config" / "sources.yaml").write_text(SOURCES_TMPL.format(
        client_id=cid, brand=a.brand, site=a.site or "", platform=a.platform, mall_id=a.mall_id,
        competitors="\n".join(f'  - name: "{c}"\n    url: ""\n    insta: ""\n    domain: ""\n    fb_query: ""' for c in comps[:5])), encoding="utf-8")
    print(f"✓ config/sources.yaml → {a.brand} ({cid})")

    if a.categories:
        mpath = ROOT / "config" / "metrics.yaml"
        m = yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}
        groups = {}
        for part in a.categories.split(";"):
            if ":" in part:
                g, names = part.split(":", 1)
                groups[g.strip()] = [n.strip() for n in names.split(",") if n.strip()]
        m["category_groups"] = groups
        mpath.write_text(yaml.safe_dump(m, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"✓ config/metrics.yaml category_groups → {list(groups)}")

    rpath = ROOT / "render.yaml"
    svc = a.service_name or f"{cid}-ops-dashboard"
    rpath.write_text(re.sub(r"(^\s*name:\s*)\S+", rf"\g<1>{svc}", rpath.read_text(encoding="utf-8"), count=1, flags=re.M),
                     encoding="utf-8")
    print(f"✓ render.yaml services[0].name → {svc}")

    dpath = ROOT / "docs" / "clients" / f"{cid}.md"
    dpath.parent.mkdir(parents=True, exist_ok=True)
    if not dpath.exists():
        dpath.write_text(CLIENT_DOC.format(brand=a.brand, client_id=cid, site=a.site or "-", platform=a.platform,
                                           mall_id=a.mall_id or "TODO", today=date.today().isoformat()), encoding="utf-8")
        print(f"✓ {dpath.relative_to(ROOT)} 생성")
    else:
        print(f"- {dpath.relative_to(ROOT)} 이미 있음(유지)")

    print("\n다음: python scripts/run_all.py --reset --mode demo --days 60 && ./scripts/dev.sh  → 틀 확인 후 docs/SETUP-GUIDE.md STEP 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
