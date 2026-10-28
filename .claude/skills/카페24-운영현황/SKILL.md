---
name: 카페24-운영현황
description: 카페24 자사몰의 '운영현황'(매출·주문·객단가·구매전환율·방문자·디바이스·카테고리·베스트·CRM·접속통계·상품 담기율·일일 브리핑) 대시보드를 신규 업체에 배포/연동하거나 점검/수정할 때 사용. 카페24 어드민 API + 카페24 통계(Analytics) API + GA4 방문자를 다룬다(광고/소재/경쟁사는 '온라인-광고' 스킬). "운영현황만 세팅", "매출 대시보드", "방문자/전환율 안 나옴", "카테고리 기타로만 나옴", "장바구니 담기율", "유입 검색어", "카페24 토큰 끊김/재인증" 같은 요청에 사용.
---

# 카페24 운영현황 (카페24 어드민 도메인)

카페24 자사몰의 **판매·방문·상품 퍼널 지표**를 매일 무인 수집해 대시보드 **"카페24 어드민" 탭**으로
보여주는 무료 자동화 도메인. 광고·소재·경쟁사는 별도 스킬(**온라인-광고**)로 분리돼 있어,
운영현황만 원하는 업체는 이 스킬만으로 세팅·운영한다.
프로젝트 루트: [`cafe24-ops-status/`](../../../cafe24-ops-status/).

## 이 도메인이 다루는 것 (카페24 어드민 탭)

- 상단 요약 카드(선택 기간 합계) + 핵심지표 기간비교(전일/전주/전년)
- 일별 매출 추이, 신규 vs 재구매, 디바이스별 매출·주문(모바일/PC)
- 방문자 상세(전체/신규/재방문/재방문율) + **방문자 추이 그래프**
- 카테고리 매출 TOP, 베스트 상품 TOP, CRM(후기 등)
- **접속통계 섹션**(같은 탭 안, 베스트 상품 바로 아래): 상품별 조회→담기→주문,
  담기율 낮은 상품 경고, 자연 검색 유입 검색어, 유입 도메인·광고채널, 회원/비회원
- **오늘의 브리핑**(전문 분석 코멘트: 전일·전주·전년, 평균 급등락, 이상치)
- **주간 리포트 탭**(별도): 지난주(월~일) vs 전주 — 한 장 요약·매체별·**구매 퍼널 병목**·
  **담기율 낮은 상품**·베스트·고객 구성·유입 검색어 + Word(.docx) 다운로드.
  매주 월요일 08:25 KST 에 `cafe24-weekly-report.yml` 이 지난주 8일을 보정 수집하고
  .docx 를 아티팩트로 올려, **9시에는 받아갈 수 있는 상태**가 된다.

**데이터 소스**: 카페24 Admin API(주문/상품/후기/품절) + **카페24 통계 API**(접속통계) + **GA4**(방문자·신규/재방문).

## 무료 스택 (모든 도메인 공통)

| 역할 | 플랫폼 | 비고 |
|---|---|---|
| 매일 수집 | GitHub Actions | `cafe24-daily-collect.yml` (07:00 KST, 최근 3일 재수집=자가치유) |
| 주간 리포트 | GitHub Actions | `cafe24-weekly-report.yml` (월 08:25 KST, 8일 보정 수집 + .docx 아티팩트) |
| 데이터 영속 | Neon Postgres | `DATABASE_URL` |
| 웹/API | Render Web Service | 무료(15분 무접속 슬립 → keepalive로 방지) |

수집 → 정규화 → 집계(`kpi_daily`) → Neon → FastAPI → React. 지표는 [`config/metrics.yaml`](../../../cafe24-ops-status/config/metrics.yaml) 선언식(코드 수정 없이 카드/표 변경).

## 카페24 통계(Analytics) API — 별도 호스트

Admin API 와 **호스트가 다르고 경로 접두어가 없다**: `https://ca-api.cafe24data.com/visitors/view`.
인증은 같은 OAuth 토큰이지만 **`mall.read_analytics` scope 필수**(없으면 전부 403 INVALID SCOPE).
공식 문서에 "승인 제휴사 대상"이라 적혀 있으나 **일반 몰 토큰으로 열린다**(2026-07-30 실측).

경로명이 직관적이지 않아 후보 60여 개를 전수 probe 해 확정했다. **아래가 사실상 스펙이니 추측으로 다시 호출하지 말 것**:

| 경로 | 주는 것 |
|---|---|
| **`/carts/action`** | 상품별 **조회→담기→담기율** ← 구매 퍼널 핵심 (`/carts/view` 아님) |
| `/products/sales` | 상품별 주문수·수량·매출 |
| `/products/view` | 상품별 조회수 |
| `/visitpaths/keywords` | 자연 검색 **실제 검색어** ← GA4 에 없음(네이버·구글이 가림) |
| `/visitpaths/domains` | 유입 도메인 |
| `/visitpaths/ads` | 광고 채널별 방문 |
| `/visitors/view` | 일자별 방문/신규/재방문 |
| `/pages/view` | 페이지 URL별 조회/방문 |
| `/members/sales` | 회원/비회원 주문수·금액 |

**없는 경로(확인됨)**: `/carts/view`·`/carts/products`, `/sales/*`, `/orders/*`, `/members/view`,
`/adeffect/*`, `/visitors/hours`·`devices`·`newandreturn`, `/pages/exit`·`entrance`,
`/products/buy`·`carts`·`best` — 총 52개. 전체 목록은 [`clients/cafe24_analytics.py`](../../../cafe24-ops-status/cafe24_ops/clients/cafe24_analytics.py) docstring.
숫자가 문자열로 오는 필드가 섞여 있다(`order_amount: "1908000"`, `add_cart_rate: "1.02"`).

### 왜 쓰나 — GA4가 못 하는 것
GA4 퍼널은 "장바구니 담기가 병목"까지만 알려주고 **어느 상품 때문인지는 모른다**.
`/carts/action` 이 상품 단위로 답한다. keek 실측: 2주간 조회 2,369회인데 담기 **0건**인 상품 발견
→ 품절/판매중지로 담을 수 없는 상품에 광고 트래픽이 흘러가고 있었다.
**담기율 0%는 "인기 없음"이 아니라 "담을 수 없는 상태"** 신호로 읽어라
(전 옵션 품절 → 판매중지 → 옵션 미설정 순으로 점검).

### 집계 시 주의
- **담기율은 기간 합계(담기÷조회)로 재계산**. API 가 주는 일자별 비율을 합산하면 100% 를 넘는다.
- **병목 판정은 중위값의 절반 미만** 기준(`cart_bottleneck`). 평균은 한 상품이 튀면 기준이 흔들린다.
- 조회 적은 상품은 비율이 요동쳐 제외(`min_views`).
- 통계 API 실패는 **예외로 올리지 않고 부분 실패로만 기록** — 보조 지표가 하루 수집 전체를 막으면 안 된다. 단 **전부 실패면 예외**로 올려 빈 결과가 기존 데이터를 덮지 않게 한다.
- 카페24 '방문'(visit_count)과 GA4 '사용자'(totalUsers)는 정의가 달라 **숫자가 안 맞는 게 정상**. 합치지 말고 나란히 두되 UI에 정의 차이를 명시(중복 카드/그래프는 넣지 않는다).

## ⚠ 카페24 토큰 — 가장 자주 터지는 곳

**refresh_token 은 갱신마다 회전하고 직전 것이 즉시 무효**다. 이 특성 때문에 사고가 두 번 났다.

1. **회전분을 저장하지 않으면 다음 실행이 죽는다.** 읽기만 하는 코드는 그 실행은 성공하고 **다음 실행이 `invalid_grant`** → 사람이 브라우저로 재인증해야 복구된다.
   → **토큰을 쓰는 모든 곳은 반드시 `Cafe24Client.from_store(config, store)`** 를 쓴다(갱신되는 그 순간 DB에 되쓴다). `from_config` 로 직접 만들지 말 것.
   "작업이 끝난 뒤 저장" 패턴도 같은 결함(중간에 죽으면 회전분 유실). 회귀 테스트: `tests/test_cafe24_token_rotation.py`.
2. **scope 를 좁히면 오류가 아니라 '지표 결측'처럼 보인다.** `read_order`/`read_customer` 만으로 재인증했다가 후기·품절·접속통계가 전부 막혔는데 화면에는 그냥 `—` 로 보였다(가장 위험한 실패 모드).
   → 필요 scope 7개: `mall.read_order,mall.read_customer,mall.read_community,mall.read_product,mall.read_category,mall.read_application,mall.read_analytics`

### 재인증(복구) 절차 — 인가코드는 **1분 만료**
1. **`cafe24-authorize-url.yml`** 실행 → 승인 URL 출력
   (client_id 는 Actions 로그 마스킹을 피하려 첫 글자만 퍼센트 인코딩. mall_id 는 호스트명이라 인코딩이 불가해 **입력값**으로 받는다)
2. 브라우저에서 승인 → 주소창 `code=` 뒤부터 `&` 앞까지 복사
3. **`cafe24-token-fast.yml`** 에 붙여넣고 실행 — checkout/setup-python/pip 없이 stdlib urllib 로 **즉시 교환(실측 2초)**. 부여된 scope 를 출력하고 누락을 경고하며 `app_kv.cafe24_token_scopes` 에 저장.

> **사람이 직접 눌러야 한다.** 코드를 에이전트에게 전달한 뒤 워크플로를 트리거하면 그 왕복에서 1분을 넘겨 `Code time expired` 가 난다(실제로 2회 실패).
> 기존 `cafe24-token-bootstrap.yml` 은 준비에 30초 이상 써서 반복 실패했다 — 복구는 `cafe24-token-fast.yml` 을 쓸 것.
> `redirect_uri` 는 개발자센터 **App관리 > Redirect URI(s)** 와 **글자까지 동일**해야 한다(다르면 `invalid_request: The redirect_uri added by Cafe24 Developers is invalid`). keek 은 `https://keek-ops-dashboard.onrender.com`(앱 URL과 동일 — 쇼핑몰 도메인이 아니다).

## 신규 업체 온보딩 (운영현황만)

1. **저장소**: repo 포크(업체=repo 1개). 2. **Neon** `DATABASE_URL` Secret 등록([`DEPLOY-FREE.md`](../../../cafe24-ops-status/DEPLOY-FREE.md) §0).
3. **카페24 앱**: 개발자센터 App 생성 → **권한선택에서 위 7개 scope 전부 체크** → Redirect URI 등록 → Secrets `CAFE24_MALL_ID`/`CLIENT_ID`/`CLIENT_SECRET`.
4. **카페24 토큰**: `cafe24-authorize-url.yml` → 승인 → `cafe24-token-fast.yml`. 이후 DB가 회전 토큰 영속([`CONNECT-GUIDE.md`](../../../cafe24-ops-status/CONNECT-GUIDE.md), [`TOKEN-LOCATIONS.md`](../../../cafe24-ops-status/TOKEN-LOCATIONS.md)).
5. **GA4**(방문자·전환율 필수): `GA4_PROPERTY_ID` + `GOOGLE_APPLICATION_CREDENTIALS_JSON`. GCP에서 **"Google Analytics Data API" 사용설정** + 서비스계정을 GA4 속성 **뷰어**로 추가([`GA4-SETUP.md`](../../../cafe24-ops-status/GA4-SETUP.md)).
6. **Render**: Blueprint → `render.yaml` → `DATABASE_URL`(+cafe24/GA4 키) → Deploy.
7. **백필**: Actions `ops daily collect` 수동 실행(`days: 30`, `skip: competitor`).
8. **검증**: `cafe24-analytics-diag.yml`(통계 API 열렸는지·scope 확인) · `keek-api-smoke.yml`(전 엔드포인트 200 + 담기율·검색어 실제 값 출력) · `cafe24-verify.yml`(정확도 리포트).

> 광고 도메인 없이 운영현황만 쓰면 광고/소재/경쟁사 수집기는 자격증명이 없어 자동 스킵된다.
> 광고 탭까지 숨기려면 `dashboard/src/App.tsx`의 `TABS`에서 해당 탭을 제거(선택).

### 업체별 필수 교체
`config/sources.yaml`(`shop.mall_id`,`brand`) · `config/metrics.yaml`(카테고리 그룹=업체 카테고리명) · `render.yaml`(`services[].name`) · keepalive/smoke/authorize 워크플로의 하드코딩 `keek-ops-dashboard.onrender.com`·`coversomeone1` · GitHub Secrets.

## 핵심 함정/교훈 (이 도메인)

- **카테고리 100% "기타"** → `/categories/{no}/products`는 422. **`/admin/products?category={N}`** 사용, `full_category_name`(dict)에서 최심 depth 추출.
- **재수집 시 합계 2배** → 차원 바뀐 낡은 행. 재삽입 전 `delete_facts(date, source)`. 단 **부분 실패 소스는 delete 없이 upsert만**(실패 채널의 기존 정상 데이터 보존).
- **방문자/전환율/신규·재방문 빔** → GA4 Data API 미사용설정 or SA 권한 없음. `cafe24-ga4-diag.yml`로 진단. 신규/재방문은 GA4 `newVsReturning`.
- **후기·품절·접속통계가 갑자기 빔** → 토큰 scope 축소 가능성. `app_kv.cafe24_token_scopes` 확인 → 7개 scope 로 재인증.
- **신규가입수·회원가입율 ⛔ 미연동 확정** → Admin `/customers/count` 는 404, `/customers` 는 `member_id` 필수라 기간 조회 불가. 통계 API 카탈로그에도 가입 지표가 없다. 스토어프론트에 GA4 `sign_up` 커스텀 이벤트를 심는 것만이 경로(범위 밖). **화면의 해당 칸이 `—` 인 것은 정상**.
- **요약 카드가 기간비교표와 안 맞음** → 요약은 선택 기간 합계여야 함(`/api/summary?from=&to=`, `summary_cards_range`). 파생지표는 합산 후 재계산.
- **조회일과 "어제"가 안 맞음** → `daysBefore`는 UTC 파싱/포맷(로컬 KST면 하루 밀림). "어제"=조회일(base) 당일.
- **라이브 "서버 오류"** → 대개 Render 슬립(keepalive) 또는 브라우저 캐시(`Ctrl+Shift+R`). 서버 진단은 `keek-api-smoke.yml`(GitHub 러너; 샌드박스는 onrender egress 차단).
- **CSS 클래스 재정의 주의** → `styles.css` 는 단일 파일이라 뒤에 붙인 규칙이 앞의 것을 덮는다(`.two-col` 을 재정의해 기존 2단 레이아웃이 바뀐 사례). 추가 전 `grep` 할 것.
- **주간 리포트가 '데이터 누적 후 지표가 채워집니다'만 나옴** → 그 주에 수집된 날짜가 없다. `scripts/weekly_report.py` 가 찍는 `missing_dates` 를 먼저 볼 것(리포트는 빈 채로도 렌더되므로 조용히 지나간다). `latest_complete_week` 는 데이터가 있는 완결 주로 폴백하므로, 탭이 지난주가 아닌 주를 보여주면 수집 구멍 신호다.
- **주간 담기 병목 표가 비어 있음** → 한 주는 조회수가 적어 월간 기본 임계값(min_views=200)이면 후보가 전멸한다. 주간은 `WEEK_MIN_VIEWS=50`. 담기 **0건**은 '인기 없음'이 아니라 '담을 수 없음'(품절·판매중지·옵션 미설정) 신호로 해석할 것.
- **월간 리포트 문구를 고칠 때** → `period_report_data` 는 주간과 공용이다. '전월' 같은 표현은 하드코딩하지 말고 `prev_word` 를 쓸 것.
- **새 수집기 추가 시** → `collectors/__init__.py` 등록 + `tests/test_pipeline.py` 의 기대 source 집합 갱신(안 하면 그 테스트만 실패).

## 레퍼런스 (이 도메인)

**API**: `/api/summary(from,to)` · `period-comparison` · `daily` · `daily-detail` · `trend` · `visitor-trend` · `digest`(브리핑+코멘트) · **`/api/shop/analytics(from,to)`**(접속통계 9블록, 비교기간 자동 계산) · **`/api/report/weekly(week)`** + **`/api/report/weekly.docx`**(week 생략 시 완결된 최근 주 자동, 아무 날짜를 줘도 그 주 월요일로 정규화) · `/api/report/monthly(.docx)` · `config/metrics` · `dates`.

**핵심 파일**
- 수집: `collectors/{cafe24,cafe24_analytics}.py` · `clients/{cafe24_client,cafe24_analytics,ga4}.py`
- 집계: `etl/{aggregate,compare,breakdown,cafe24_analytics}.py` · `alerts.py`(브리핑/코멘트)
- 리포트: `etl/monthly_report.py`(**기간 무관 코어 `period_report_data`**) ← `etl/weekly_report.py`(주 경계 + keek 전용 항목) → `report_docx.py`(월간·주간 공용 Word) · `scripts/weekly_report.py`(CI 용 .docx 생성)
- 화면(리포트): `pages/WeeklyReportPage.tsx` · `pages/MonthlyReportPage.tsx` (섹션 번호는 그려지는 섹션만 순서대로 매겨진다)
- 화면: `pages/Cafe24Page.tsx` + `components/ShopAnalyticsSection.tsx`(접속통계 — 베스트 상품 뒤에 삽입, 데이터/권한 없으면 이 섹션만 조용히 접힘)
  나머지 컴포넌트(렌더 순서): RangePicker → SummaryCards → PeriodTable → SalesChart → NewReturningChart·AdCostChart → DeviceDonut·DevicePerfTable → VisitorDetailCard·SignupTrendChart → VisitorChart → CategoryBar → BestTable → **ShopAnalyticsSection** → DailyTable → PlannedGroups. 상단 BriefingBanner 는 `App.tsx` 소관.
- 토큰: `scripts/{cafe24_auth,cafe24_authorize_url}.py` · 워크플로 `cafe24-{authorize-url,token-fast,token-bootstrap,token-reset}.yml`
- 진단: `scripts/{cafe24_analytics_diag,ga4_diag,diag_endpoints,verify}.py`

**로컬**: `python scripts/run_all.py --mode live --days 30` · `uvicorn api.main:app --reload` · `cd dashboard && npm run build` · `pytest`.
