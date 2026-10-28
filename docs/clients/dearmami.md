# 디어마미 (dearmami) — 온보딩 기록

생성일: 2026-10-28 · 사이트: https://dearmami.co.kr · 플랫폼: cafe24(추정, 확인 필요) · 몰 아이디: `TODO`

## 0. 업체와 합의할 것
- [ ] **쇼핑몰 플랫폼이 카페24인지** — 어드민 주소 `https://<몰아이디>.cafe24.com` 확인 → `config/sources.yaml` `shop.mall_id`
      (구축 세션에서는 dearmami.co.kr 접근이 차단되어 직접 확인 못 함. 검색상 '디얼마미' 중년 여성 의류 브랜드로 추정)
- [ ] 덩어리: **A 운영현황 + B 광고** (1차 목표 = 매출 대시보드)
- [ ] 실제 집행 중인 광고 채널 (Meta / 네이버SA / 카카오 / 구글 중)
- [ ] 카페24 상품 카테고리명 → `config/metrics.yaml` `category_groups` (현재는 여성 의류 일반값: 원피스·블라우스/셔츠·니트/가디건·팬츠·스커트·아우터)
- [ ] 경쟁사 브랜드명 최대 5개 → `config/sources.yaml` `competitors` (현재 placeholder)
- [ ] 담당자 1명 (카페24 어드민·GA4·Meta 비즈니스·네이버 광고 로그인 권한)

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
| 9 | Neon / GitHub / Render | DATABASE_URL, Secrets, Blueprint(`dearmami-ops-dashboard`) | 배포 URL | [ ] |

## 2. 진행 로그
- 2026-10-28: 대시보드 틀 구축(운영현황·광고·채널 연결 3탭), 데모 60일 데이터로 링크 게시. `new_client.py` 로 디어마미 설정 적용.
- 다음: 담당자에게 §0·§1 전달 → 카페24 Client ID/Secret 수령 시 STEP 1 진행.

## 3. 업체 특이사항
- 중년 여성 의류 (원피스 중심 추정) → 카테고리 그룹은 실제 카페24 카테고리명 확인 후 교체
- 11번가 등 오픈마켓 병행 판매 가능성 → 오픈마켓 매출은 이 대시보드 범위 밖(카페24 자사몰만). 필요 시 별도 수집기 추가
