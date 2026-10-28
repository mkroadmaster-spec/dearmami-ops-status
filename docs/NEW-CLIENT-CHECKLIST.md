# 신규 업체 이식 체크리스트 — 대시보드 + SNS 자동운영

keek(pslab) 에서 구축한 시스템을 **다른 업체에 그대로 옮길 때** 필요한 것 전부.
구성은 세 덩어리이고, 업체가 원하는 것만 고르면 된다.

| 덩어리 | 무엇 | 스킬 | 소요 |
|---|---|---|---|
| **A. 운영현황 대시보드** | 카페24 매출·주문·방문·담기율·일일 브리핑·주간/월간 리포트 | `카페24-운영현황` | 반나절 |
| **B. 광고 대시보드** | Meta·네이버SA·구글·카카오 광고 성과 + 소재 히스토리 + 경쟁사 | `온라인-광고` | 반나절 (토큰 발급 대기 제외) |
| **C. SNS 자동운영** | 인스타·스레드·블로거·유튜브 쇼츠 매일 자동 발행 + 학습 루프 | `sns-auto-operation` | 1일 + 레퍼런스 수집 |

> A·B 는 한 저장소/한 서버(`cafe24-ops-status`)에 같이 올라가고, C 는 별도 저장소(`<업체>-sns`)로 분리한다.

---

## 0. 먼저 결정할 것 (업체와 합의)

- [ ] 쇼핑몰 플랫폼이 **카페24** 인가? (A 는 카페24 전용. 다른 플랫폼이면 수집기 새로 작성)
- [ ] 어느 덩어리를 쓸지 (A만 / A+B / A+B+C)
- [ ] 광고 채널 중 실제 집행 중인 것 (없는 채널은 자격증명 없이 두면 자동 스킵)
- [ ] 업체 측 **담당자 1명** — 각 플랫폼 로그인·권한을 가진 사람 (토큰 발급은 대부분 이 사람이 해야 함)
- [ ] 비용 승인: Render Starter $7/월(선택) · 클로드 API 월 1~2천원(Haiku, C만)

---

## 1. 플랫폼 계정 (무료, 우리가 만들거나 업체 계정에 초대)

| 플랫폼 | 용도 | 플랜 | 메모 |
|---|---|---|---|
| **GitHub** | 코드 + 매일 수집 크론 + 시크릿 보관 | 무료 | 업체당 저장소 1개 (포크). Private 권장 |
| **Neon** | Postgres (수집 데이터 영속) | 무료 | `DATABASE_URL` 발급. 없으면 토큰 회전이 안 남아 무인 수집 깨짐 |
| **Render** | 대시보드 웹 서버 | 무료 / Starter $7 | 무료는 15분 뒤 잠듦(첫 접속 30~60초). 10분 keepalive 는 깃허브가 미뤄서 불완전 |
| **Google Cloud** | GA4 Data API 서비스계정 (+ C 의 Blogger·YouTube OAuth) | 무료 | 프로젝트 1개 |
| **Slack** (선택) | 수집 실패·주간 리포트 알림 | 무료 | Webhook URL. **없으면 토큰 끊겨도 아무도 모름** (keek 36일 결측 사례) |
| **Telegram** (선택, C) | 발행 알림 | 무료 | 봇 토큰 + chat id |

---

## 2. A — 운영현황 대시보드: 연결 정보

### 업체 담당자가 발급해야 하는 것

| 항목 | 어디서 | GitHub Secret 이름 |
|---|---|---|
| 카페24 몰 아이디 | 카페24 어드민 주소 `https://<여기>.cafe24.com` | `CAFE24_MALL_ID` |
| 카페24 앱 Client ID / Secret | developers.cafe24.com → 앱 생성 → **권한 7개 전부 체크**(아래) → Redirect URI = 대시보드 주소 | `CAFE24_CLIENT_ID` `CAFE24_CLIENT_SECRET` |
| 카페24 토큰 (최초 1회) | Actions `cafe24 authorize url` → 브라우저 승인 → `cafe24 token fast` (**코드 1분 만료, 담당자가 직접 클릭**) | DB 에 자동 저장 |
| GA4 속성 ID | GA4 관리 → 속성 설정 → 숫자만 | `GA4_PROPERTY_ID` |
| GA4 서비스계정 키 | Google Cloud → 서비스계정 → JSON 키 → **GA4 속성에 뷰어로 추가** + "Google Analytics Data API" 사용설정 | `GOOGLE_APPLICATION_CREDENTIALS_JSON` |

**카페24 앱 scope 7개 (하나라도 빠지면 해당 지표가 조용히 빔)**
`mall.read_order` `mall.read_customer` `mall.read_community` `mall.read_product` `mall.read_category` `mall.read_application` `mall.read_analytics`

### 코드에서 바꿀 곳

- `config/sources.yaml` — `shop.mall_id`, `brand`
- `config/metrics.yaml` — 카테고리 그룹(업체 카테고리명)
- `render.yaml` — `services[].name`
- `.github/workflows/keek-*.yml`, `cafe24-authorize-url.yml` — 하드코딩 도메인 `keek-ops-dashboard.onrender.com`, `coversomeone1`
- `dashboard/index.html` `<title>`, `cafe24_ops/report_docx.py` 리포트 제목 "keek"

### 못 하는 것 (미리 말해둘 것)
- **신규가입수·회원가입율** — 카페24 API 로 조회 불가. 화면 `—` 정상
- **GA4 A→B→C 경로 추적** — BigQuery 내보내기 없이는 불가. 단계별 건수 감소로만 봄

---

## 3. B — 광고 대시보드: 연결 정보

| 채널 | 담당자가 발급 | Secret 이름 | 함정 |
|---|---|---|---|
| **Meta** | business.facebook.com → 비즈니스 설정 → **시스템 사용자** → 토큰 생성(**만료되지 않음**, `ads_read` `read_insights`) + 앱 ID/시크릿 + 광고계정 ID(`act_` 뒤 숫자) | `META_ACCESS_TOKEN` `META_APP_ID` `META_APP_SECRET` `META_AD_ACCOUNT_ID` | 그래프 탐색기 토큰은 **60일 만료** → 반드시 시스템 사용자. 담당자가 **전체 액세스 권한** 이어야 메뉴가 보임 |
| **네이버 검색광고** | searchad.naver.com → 도구 → API 사용 관리 → 액세스 라이선스·비밀키(1회 노출) + CUSTOMER_ID | `NAVER_SA_API_KEY` `NAVER_SA_SECRET_KEY` `NAVER_SA_CUSTOMER_ID` | 파워링크/플레이스 자동 분리 |
| **구글 광고** | ads.google.com MCC → API 센터 개발자 토큰 + OAuth refresh token + Customer ID | `GOOGLE_ADS_DEVELOPER_TOKEN` `GOOGLE_ADS_ACCESS_TOKEN` `GOOGLE_ADS_CUSTOMER_ID` `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | 개발자 토큰 운영 승인에 수일. refresh 자동갱신은 아직 미구현 |
| **카카오 모먼트** | 카카오 비즈니스 → 광고계정 ID + 액세스 토큰 | `KAKAO_ACCESS_TOKEN` `KAKAO_AD_ACCOUNT_ID` | |
| **네이버 오픈API** (경쟁사 검색/트렌드) | developers.naver.com → 애플리케이션 → Client ID/Secret | `NAVER_CLIENT_ID` `NAVER_CLIENT_SECRET` | 무료, 즉시 |
| **크리테오·네이버 GFA·브랜드검색** | ❌ 연동 없음 — 유입은 GA4 에 잡히지만 **광고비가 없어 ROAS 과대** | — | 업체에 미리 고지 |

### 코드에서 바꿀 곳
- `config/sources.yaml` — `ads[].account_id`, `competitors[]`(경쟁사 브랜드명), `region_status`/`competitor_media` 구글시트 ID(쓰면)
- 리드젠 업체(자사몰 없음)면 **dbrick-ads-status** 구조(문의·CPA 중심)가 맞고, 이커머스면 **cafe24-ops-status**(매출·ROAS)

---

## 4. C — SNS 자동운영: 연결 정보

### AI·도구
| 도구 | 용도 | 비용 | Secret |
|---|---|---|---|
| **클로드 API** (Anthropic) | 글·캡션 생성 | Haiku 월 1~2천원 | `ANTHROPIC_API_KEY` (+ Variables `PSLAB_CLAUDE_MODEL=claude-haiku-4-5`) |
| **Gemini** (선택) | 카드 이미지 생성 | 무료 할당 | `GEMINI_API_KEY` |
| **힉스필드** | 릴스/쇼츠 장면 클립 (seedance) | 웹 무료 프로모 우선, MCP 는 크레딧 | MCP 연결(세션) — 클립은 `clip-library.json` 재사용 |
| **Pexels** (선택) | 배경 실사진 | 무료 | `PEXELS_API_KEY` |
| **imgbb** | 인스타 발행용 이미지 호스팅 | 무료 | `IMGBB_API_KEY` |
| ffmpeg / 크로미움 | 쇼츠 합성·카드 렌더 | CI 내장 | — (**로컬 렌더 금지**, CI 에서만) |

### 채널 토큰 (담당자 발급) — 접두어 `<업체>_`
| 채널 | 자동 발행 | Secret |
|---|---|---|
| 인스타그램 | ✅ | `_INSTAGRAM_ACCESS_TOKEN` `_INSTAGRAM_IG_USER_ID` `_FB_APP_ID` `_FB_APP_SECRET` |
| 스레드 | ✅ | `_THREADS_ACCESS_TOKEN` `_THREADS_THREADS_USER_ID` `_THREADS_APP_ID` `_THREADS_APP_SECRET` |
| 구글 블로그 | ✅ | `_BLOGGER_BLOG_ID` `_BLOGGER_CLIENT_ID` `_BLOGGER_CLIENT_SECRET` `_BLOGGER_REFRESH_TOKEN` |
| 유튜브 쇼츠 | ✅ | `_YOUTUBE_CHANNEL_ID` `_YOUTUBE_CLIENT_ID` `_YOUTUBE_CLIENT_SECRET` `_YOUTUBE_REFRESH_TOKEN` |
| 링크드인 | ✅ | `_LINKEDIN_ACCESS_TOKEN` `_LINKEDIN_AUTHOR_URN` |
| **네이버 블로그** | ❌ **수동** (공식 API 없음) | 대시보드에서 본문 복사 + 이미지 다운로드 |

### 업체가 줘야 하는 자료
- 구글 드라이브 `※alway on/<n>. <업체>/1. 레퍼런스 모음/` — **채널별 레퍼런스·지침** (비어 있으면 기획 시작 안 함)
- 브랜드 키워드(상시 포함어), 톤앤매너, 금칙어
- 발행 시각·빈도 (기본 하루 2건, 릴스 15초 무음)

---

## 5. 순서 (실제로 하는 차례)

1. GitHub 저장소 포크 → Neon `DATABASE_URL` → Secrets 등록
2. 코드 치환 (§2·§3 "바꿀 곳") → 푸시
3. Render Blueprint 배포 (`render.yaml`) → 환경변수에 `DATABASE_URL` + 카페24/GA4 키
4. 카페24 토큰 1회 승인 (담당자 클릭)
5. Actions `ops daily collect` 수동 실행 `days: 30`, `skip: competitor` → 백필
6. 검증 워크플로: `cafe24-analytics-diag`(scope) · `keek-api-smoke`(전 엔드포인트) · `cafe24-verify`(정확도)
7. 광고 토큰 들어오는 대로 B 채널 추가 (없는 채널은 자동 스킵)
8. C 는 별도 저장소에서 `sns-auto-operation` 스킬 §3 순서대로

---

## 6. 반드시 피할 사고 (keek 에서 실제로 난 것)

- **카페24 refresh_token 회전** — 읽기만 하고 되쓰지 않는 스크립트 1회로 체인이 끊김. `from_store` 만 쓸 것
- **scope 축소 재인증** — 후기·품절·통계가 **오류 없이 빈 값**으로 보임. 7개 전부
- **Meta 60일 토큰** — 만료돼도 로그에 401 만 남음 → 36일 결측. 시스템 사용자 토큰 + Slack 알림
- **DB 토큰이 Secret 보다 우선** — 키 재발급 후 `cafe24 token reset` 으로 DB 옛 토큰을 비워야 함
- **Render 빌드 필터 없음** — SNS 봇이 하루 3번 커밋할 때마다 전체 재빌드 → 무료 빌드 분 소진. `buildFilter.paths` 필수
- **data/ 커밋 전 git fetch** — 오래된 체크아웃 커밋 시 `published` 가 되돌아가 **중복 발행**
- **로컬 이미지 렌더 금지** — 세션 크로미움은 하단 85px 흰 띠. CI 에서만
- **멀티테넌트 Secrets 충돌** — 같은 저장소에 두 업체면 `TENANT_` 접두어. 권장은 **업체당 저장소 분리**
