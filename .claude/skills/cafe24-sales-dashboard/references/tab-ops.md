# 탭 1 · 카페24 어드민 (`#ops`)

쇼핑몰 자체의 성과를 본다: 얼마 팔렸는지, 누가 샀는지, 무엇이 팔렸는지, 어디서 들어왔는지.

전체 배치: `screens/ops-00-full.png` · 화면 코드: `dashboard/index.html` 의 `section#tab-ops` + `loadOps()`
한 번에 부르는 API: `/api/summary` `/api/daily` `/api/breakdown` `/api/shop/analytics` `/api/period-comparison`

## 목차

1. KPI 카드
2. 핵심 지표 기간 비교
3. 일별 매출 추이 · 신규 vs 재구매 매출
4. 광고비 vs 비광고 매출 · 디바이스
5. 방문자 상세 · 신규 방문·첫 구매 추이
6. 방문자 추이
7. 카테고리 매출 · 베스트 상품 TOP 10
8. 상품별 조회 → 담기 → 주문
9. 유입 검색어 · 담기율 낮은 상품 경고
10. 유입 도메인 · 광고 채널별 방문
11. 회원·비회원 매출 · 페이지뷰 TOP
12. 일별 운영 데이터 · 세부 구성

---

## 1. KPI 카드

캡처: `screens/ops-01-kpi-cards.png`

- **보여주는 것**: 매출 · 주문수 · 객단가 · 방문자 · 구매전환율 · 광고비 · ROAS — 선택 기간 합계와 비교기간 대비 증감
- **출처**: `/api/summary` → `kpi_daily` 테이블을 기간 합산
- **계산**: 객단가 = 매출 ÷ 주문수, 구매전환율 = 주문수 ÷ 방문자 × 100, ROAS = 광고매출 ÷ 광고비
- **코드**: 카드 구성은 `config/metrics.yaml` 의 `summary_cards` (코드 수정 없이 바꿀 수 있다). 계산은 `cafe24_ops/etl/aggregate.py: derive()`
- **주의**: 방문자는 GA4 가 연결돼 있으면 GA4 사용자, 없으면 카페24 접속통계의 '방문'이다. 두 정의가 달라 숫자가 다르다(정상). 전환율도 그에 따라 달라진다.

## 2. 핵심 지표 기간 비교

캡처: `screens/ops-02-period-compare.png`

- **보여주는 것**: 조회일 하루의 12개 지표(매출·주문건수·객단가·방문자·구매전환율·신규 주문·재구매 주문·총 광고비·ROAS·매출대비 광고비·모바일 비중·후기)를 **전일 / 전주 같은 요일 / 전년 같은 날**과 나란히
- **출처**: `/api/period-comparison?date=` → `breakdown.period_comparison()`
- **주의**: 기간 선택과 무관하게 **조회일 하루** 기준이다. 전년 데이터가 없으면 `—`.

## 3. 일별 매출 추이 · 신규 vs 재구매 매출

캡처: `screens/ops-03-daily-sales_new-vs-returning.png`

- **일별 매출 추이**: 날짜별 매출 막대. 아래 작은 선은 **이번 달 누적 매출 vs 목표 페이스**(점선).
  - 목표는 `config/metrics.yaml` 의 `targets.monthly_sales`. 0 이면 목표선이 안 나온다. 일할 목표 = 월 목표 ÷ 30.
- **신규 vs 재구매 매출**: 날짜별 신규 고객 매출과 재구매 고객 매출(누적 영역).
  - 신규 = 카페24 주문의 `first_order == "T"`(그 고객의 첫 주문).
- **출처**: `/api/daily` (`kpi_daily` 의 `gross_sales`, `new_sales`, `returning_sales`)
- **수집**: `cafe24_ops/collectors/cafe24.py` — 결제일(`pay_date`) 기준, 취소 주문 제외, 금액은 `payment_amount`

## 4. 일별 광고비 vs 비광고 매출 · 디바이스

캡처: `screens/ops-04-ad-vs-organic_device.png`

- **광고비 vs 비광고 매출**: 날짜별 광고 전환매출(주황) + 비광고 매출(파랑) 누적 막대, 옆에 광고비(노랑).
  - 비광고 매출 = 전체 매출 − 광고 전환매출(0 미만이면 0). 광고 플랫폼이 보고한 매출을 빼는 것이라 **추정치**다.
- **디바이스별 매출 비율**: 모바일/PC 도넛. **디바이스별 상세**: 매출·주문·객단가·비중 표.
  - 모바일 = 주문의 `order_from_mobile == "T"`.

## 5. 방문자 상세 · 신규 방문·첫 구매 추이

캡처: `screens/ops-05-visitors_first-purchase.png`

- **방문자 상세**: 타일 6개 — 방문자 · 신규 방문 · 재방문 · 재방문율 · 카페24 방문 · 페이지뷰(상위 페이지 합계)
- **신규 방문·첫 구매 추이**: 신규 방문(초록 막대)·첫 주문(주황 막대)·첫 구매 전환율(보라 선, 오른쪽 축). 아래에 기간 합계 문장.
  - 첫 구매 전환율 = 첫 주문 ÷ 신규 방문 × 100
- **출처**: 카페24 통계 API `/visitors/view` → facts `cafe24_analytics` 의 `visit_count`·`first_visit_count`·`re_visit_count`
- **주의**: **회원가입 수는 표시하지 못한다.** 카페24 가입자 조회는 개인정보 권한(`mall.read_privacy`)이 필요해서, 권한이 없으면 403 이 난다. 그래서 '신규회원' 대신 '신규 방문·첫 구매'로 대체했다. 사용자가 그 권한으로 재동의하면 가입 수를 붙일 수 있다.

## 6. 방문자 추이

캡처: `screens/ops-06-visitor-trend.png`

- **보여주는 것**: 날짜별 전체 방문(영역)·신규 방문·재방문 세 선
- **출처**: `/api/daily` 의 `visitors`·`new_visitors`·`returning_visitors`. GA4 가 없으면 카페24 접속통계 값이 들어간다(`aggregate.kpis_from_facts()`).

## 7. 카테고리 매출 · 베스트 상품 TOP 10

캡처: `screens/ops-07-category_best-products.png`

- **카테고리 매출**: 카테고리별로 선택기간(파랑)·비교기간(회색) 막대를 나란히. 이름 옆에 ▲▼ 증감률. 아래에 **비교기간 대비 매출 증감액** 막대(증가 초록 / 감소 빨강).
- **베스트 상품 TOP 10**: 순위·상품·카테고리·매출·비교기간 매출·증감·순위 변화(▲3 / ▼2 / 신규). 아래에 **상품별 매출 증감액** 막대.
- **출처**: `/api/breakdown` → `breakdown.category_sales()`, `breakdown.best_products()` (둘 다 비교기간 값 포함)
- **카테고리 판정이 핵심이다**: 카페24 주문 품목에는 카테고리가 **들어 있지 않다**. 그대로 두면 매출이 전부 '기타'가 된다.
  - `cafe24_ops/etl/category_map.py` 가 상품 상세 API(`/admin/products/{no}` 의 `category` 목록)와 카테고리 트리(`/admin/categories`)로 상품마다 그룹을 정한다.
  - 그룹 정의는 `config/metrics.yaml` 의 `category_groups` (예: `원피스: ["원피스", "소매원피스", …]`). 상품이 속한 카테고리 경로를 **깊은 단계부터** 이름으로 대조하고, 여러 그룹에 걸리면 많이 걸린 쪽을 택한다. 세일·NEW·BEST 같은 기획전 카테고리는 이름이 안 맞아 자동으로 빠진다.
  - 결과는 DB `app_kv` 의 `cafe24_product_category` 에 쌓는다. 집계할 때 상품번호로 붙이므로 **분류를 바꾸면 과거 매출에도 바로 반영**된다(재수집 불필요).
  - 새 업체에서는 `scripts/category_probe.py` 로 카테고리 트리를 먼저 보고 그룹을 정한 뒤 `scripts/category_fill.py` 로 과거 판매 상품을 한 번 채운다(1만 상품에 약 1시간).

## 8. 상품별 조회 → 담기 → 주문

캡처: `screens/ops-08-product-funnel.png`

- **보여주는 것**: 상품별 조회수(막대 포함)·담기·담기율·주문·담기→주문·조회→주문. 조회·담기율·주문 숫자 아래에 비교기간 대비 변화(▲▼, 담기율은 %p). 맨 아래 합계 행.
- **태그**: `병목` = 담기율이 전체 중위값의 절반 미만 / `담기 0 · 담을 수 없는 상태?` = 조회는 있는데 담기가 0건(품절·판매중지·옵션 미설정 의심)
- **출처**: `/api/shop/analytics` → `breakdown.cart_funnel()` — 카페24 통계 API `/products/view`(조회), `/carts/action`(담기), `/products/sales`(주문)
- **계산**: 담기율 = 기간 담기 합 ÷ 기간 조회 합(날짜별 비율을 평균하지 않는다). 조회수 기준 미만 상품은 제외(7일 이하 50, 그보다 길면 200).
- **주의**: 카페24 통계는 같은 상품이 이름(페이지 제목)별로 여러 행으로 온다. 그래서 **상품번호로 묶는다**. 조회는 합, 담기는 최댓값.

## 9. 자연 검색 유입 검색어 · 담기율 낮은 상품 경고

캡처: `screens/ops-09-keywords_low-cart.png`

- **유입 검색어**: 검색어·방문·비중·비교기간 대비. 비교기간에 없던 검색어는 `신규 ★`.
- **담기율 경고**: 8번 표에서 `병목` 또는 `담기 0`인 상품만 최대 10개.
- **출처**: 통계 API `/visitpaths/keywords` → facts `keyword_visits`

## 10. 유입 도메인 · 광고 채널별 방문

캡처: `screens/ops-10-domains_ad-paths.png`

- **유입 도메인**: 어느 사이트에서 들어왔는지(naver.com, instagram.com …). **광고 채널별 방문**: 카페24 가 광고로 분류한 유입.
- **출처**: 통계 API `/visitpaths/domains`, `/visitpaths/ads` → facts `domain_visits`, `adpath_visits`
- **주의**: 광고 채널 이름은 응답의 `ad` 필드다(`ad_channel` 이 아니다 — 잘못 읽으면 전부 빈 이름으로 합쳐진다).

## 11. 회원 · 비회원 매출 · 페이지뷰 TOP

캡처: `screens/ops-11-members_pageviews.png`

- **회원·비회원**: 주문·금액·객단가. 통계 API `/members/sales` 는 한 행에 `member_order_*`, `nonmember_order_*` 가 같이 온다.
- **페이지뷰 TOP**: 통계 API `/pages/view` 의 `count`.

## 12. 일별 운영 데이터 · 세부 구성

캡처: `screens/ops-12-daily-table_composition.png`

- **일별 운영 데이터**: 최근 14일의 날짜별 13개 지표 표(`kpi_daily` 그대로).
- **세부 구성**: 어떤 지표가 어떤 소스로 채워졌는지 ✓/○ 칩(매출=카페24 Admin, 방문자=GA4, 접속통계=카페24 통계, 광고비=광고 채널 …). 사용자가 "이 칸이 왜 비었지?"를 물으면 여기를 먼저 본다.

---

## 카페24 통계 API 응답 모양 (실제 확인한 것)

문서와 실제가 달라 처음엔 전부 0 으로 저장됐다. 새 업체에서 숫자가 0 이면 `scripts/analytics_probe.py` 로 응답 모양부터 본다.

| 경로 | 목록 키 | 주요 필드 |
|---|---|---|
| `/visitors/view` | `view` | `visit_count`, `first_visit_count`, `re_visit_count` |
| `/carts/action` | `action` | `product_no`, `product_name`, `count`, `add_cart_count`, `add_cart_rate` |
| `/products/sales` | `sales` | `order_count`, `order_product_count`, `order_amount` |
| `/products/view` | `view` | `product_no`, `product_name`, `count` |
| `/visitpaths/ads` | `ads` | `ad`, `visit_count` |
| `/pages/view` | `view` | `url`, `count`, `visit_count`, `first_visit_count` |
| `/members/sales` | `sales` | `member_order_count`, `member_order_amount`, `nonmember_order_count`, `nonmember_order_amount` |

- 호스트는 `ca-api.cafe24data.com`, `limit` 최대 1000, `offset` 지원.
- DB 용량 때문에 하루 저장 상한을 둔다: 상품 100, 판매 상품 50, 검색어 100, 도메인 50, 페이지 30 (`collectors/cafe24_analytics.py`).
