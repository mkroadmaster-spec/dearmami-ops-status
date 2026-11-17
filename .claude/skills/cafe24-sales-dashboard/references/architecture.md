# 구조 — 데이터가 화면까지 오는 길

## 목차

1. 한눈에 보는 흐름
2. 폴더 구조
3. DB 테이블 4개
4. 수집기와 facts source
5. 지표 계산식
6. API 목록
7. 설정 파일
8. 새로 추가할 때 (지표·그래프·탭·채널)

---

## 1. 한눈에 보는 흐름

```
외부 API ──▶ clients/*.py ──▶ collectors/*.py ──▶ facts (원본, 날짜·소스·지표·dims)
(카페24·광고)   (인증·호출)      (표준 형식으로)          │
                                                        ▼ etl/aggregate.py
                                                   kpi_daily (하루 한 줄 지표)
                                                        │
                    etl/breakdown.py · period_report.py · alerts.py (조회 시 계산)
                                                        ▼
                              api/main.py (FastAPI /api/*)
                                 │                        │
                        서버로 볼 때 (uvicorn)     scripts/export_static.py
                                                   (API 응답을 통째로 HTML 에 저장)
                                                          ▼
                                             GitHub Pages (서버 없는 공개 페이지)
```

- **매일 07:00 KST**: GitHub Actions `daily-collect.yml` 이 최근 3일을 수집 → Neon(Postgres)에 저장
- **매일 07:40 KST**: `pages-deploy.yml` 이 Neon 에서 읽어 정적 페이지를 만들어 배포
- 화면을 보는 사람은 정적 페이지만 본다. DB 에 직접 접속하지 않는다.

## 2. 폴더 구조

```
cafe24_ops/
  config.py            환경변수·yaml 읽기 (env(), env_all(), mode())
  store.py             DB (SQLite 기본, DATABASE_URL 있으면 Postgres). 끊긴 연결 자동 재연결
  pipeline.py          run_day / run_range — 수집기 실행 → facts → kpi_daily
  alerts.py            오늘의 브리핑 (digest)
  report_docx.py       리포트 → Word
  clients/             채널별 API 클라이언트 (채널당 파일 1개)
  collectors/          수집기 (표준 Fact 로 변환) + demo.py (데모 생성기) + __init__.py (REGISTRY)
  etl/
    aggregate.py       facts → kpi_daily, 기간 합산, 파생지표
    breakdown.py       화면용 집계 전부 (채널별·카테고리·퍼널·소재·키워드…)
    category_map.py    상품번호 → 카테고리 그룹
    period_report.py   주간·월간 리포트
api/main.py            FastAPI 엔드포인트
dashboard/index.html   화면 전체 (단일 파일) · dashboard/vendor/chart.umd.js
scripts/               실행 스크립트 (run_all, export_static, *_auth, *_probe …)
config/                sources.yaml · metrics.yaml · secrets.env.example
.github/workflows/     수집·배포·토큰·진단 워크플로
tests/                 pytest (파이프라인·토큰 회전)
docs/                  사용자용 가이드
data/manual/<채널>/    CSV 업로드 채널
```

## 3. DB 테이블 4개 (`store.py`)

| 테이블 | 열 | 용도 |
|---|---|---|
| `facts` | date, source, metric, dims(JSON), value — 다섯 열 중 앞 넷이 기본키 | 수집 원본. 모든 화면 숫자의 근원 |
| `kpi_daily` | date, metric, value | 하루 한 줄 요약 지표(facts 에서 계산). KPI 카드·일별 그래프용 |
| `app_kv` | key, value, updated_at | 토큰(카페24·카카오·구글·GFA), 캐시(상품 카테고리·카카오 소재 메타), `data_mode`, `last_run_at` |
| `collect_log` | run_at, date, source, status, message | 수집 기록 (채널 연결 탭) |

- `facts` 의 dims 는 정렬된 JSON 문자열이다(예: `{"channel": "kakao"}`). 같은 날짜·소스·지표·dims 는 한 행이라 다시 수집해도 중복되지 않는다.
- Neon 무료 한도는 0.5GB. `facts` 한 행이 약 0.4KB(인덱스 포함)다. 용량 관리는 `operations.md`.

## 4. 수집기와 facts source (`collectors/__init__.py: REGISTRY`)

| 수집기 | facts source | 주요 metric | dims |
|---|---|---|---|
| `cafe24` | `cafe24` | gross_sales, orders, new_orders, returning_orders, new_sales, returning_sales, mobile_sales, pc_sales, mobile_orders, pc_orders, canceled_orders, soldout_products, product_sales | product_sales 만: product_no, product, category |
| `cafe24_analytics` | `cafe24_analytics` | visit_count, first_visit_count, re_visit_count, product_views, product_cart_adds, product_orders, product_qty, product_amount, keyword_visits, domain_visits, adpath_visits, page_views, member_orders, member_sales | product_no·product / keyword / domain / ad_channel / path / member_type |
| `ga4` | `ga4`, `ga4_channel`, `ga4_page`, `ga4_event` | visitors, sessions, pageviews, new_visitors, returning_visitors, conversions, avg_session_sec / event_count | source_medium / path / event |
| `ads` | `ads` | ad_cost, impressions, clicks, conversions, ad_revenue | channel |
| `creative` | `creative` | 위 5개 + reach, frequency | ad_id, ad_name, campaign, adset, thumbnail_url |
| `google_creative` | `google_creative` | 위 5개 | + ad_type |
| `kakao_creative` | `kakao_creative` | 위 5개 | + ad_type |
| `naver_keyword` | `naver_keyword`, `naver_place` | 위 5개 | keyword_id, keyword, adgroup, campaign / adgroup_id |
| `competitor` | `competitor` | trend_ratio | brand |

**파이프라인 규칙** (`pipeline.run_day`):
- 수집기의 `is_configured()` 가 거짓이면 `skip`.
- 성공하면 그 날짜·소스의 기존 facts 를 지우고 새로 넣는다(낡은 행 제거).
- `PartialFailure`(일부 채널만 실패)면 지우지 않고 받은 것만 덧쓴다.
- 전부 실패하면 예외 → `fail` 기록, 기존 데이터는 그대로.
- `ADS_ONLY=naver_sa` 처럼 광고 채널 일부만 수집할 때는 `ads` 를 지우지 않는다(다른 채널 보존).
- 마지막에 `aggregate_day()` 로 그 날의 `kpi_daily` 를 다시 만든다.

## 5. 지표 계산식 (`etl/aggregate.py`)

**더할 수 있는 값**(`ADDITIVE`)만 기간 합산한다: 매출·주문·신규/재구매·모바일/PC·방문·세션·페이지뷰·광고비·광고매출·클릭·노출·전환.

**비율은 합산 후 다시 계산한다** (`derive()`):

| 지표 | 키 | 식 |
|---|---|---|
| 객단가 | `aov` | 매출 ÷ 주문수 |
| 구매전환율 | `conversion_rate` | 주문수 ÷ 방문자 × 100 |
| ROAS | `roas` | 광고매출 ÷ 광고비 × 100 (화면은 ÷100 해서 `x`) |
| CTR | `ctr` | 클릭 ÷ 노출 × 100 |
| CPC | `cpc` | 광고비 ÷ 클릭 |
| CPA | `cpa` | 광고비 ÷ 전환 |
| 광고 전환율 | `cvr` | 전환 ÷ 클릭 × 100 |
| 매출대비 광고비 | `ad_cost_ratio` | 광고비 ÷ 매출 × 100 |
| 모바일 비중 | `mobile_share` | 모바일 매출 ÷ 매출 × 100 |
| 재방문율 | `revisit_rate` | 재방문 ÷ 방문자 × 100 |
| 평균 체류 | `avg_session_sec` | 체류 총합 ÷ 세션 |
| 비광고 매출 | `organic_sales` | 매출 − 광고매출 (0 미만이면 0) |

방문자는 GA4 우선, 없으면 카페24 접속통계 '방문'.

## 6. API 목록 (`api/main.py`)

모든 데이터 API 는 `from`, `to`, `cmp_from`, `cmp_to` 를 받는다. 비교기간을 안 주면 직전 같은 길이.

| 경로 | 쓰는 곳 | 함수 |
|---|---|---|
| `/api/config` `/api/dates` | 헤더 | config, store.date_bounds |
| `/api/digest?date=` | 오늘의 브리핑 | alerts.digest |
| `/api/summary` | KPI 카드 | aggregate.sum_range + compare |
| `/api/period-comparison?date=` | 핵심 지표 기간 비교 | breakdown.period_comparison |
| `/api/daily` | 일별 그래프·표 | store.kpi_range + derive |
| `/api/breakdown` | 카테고리·베스트 | category_sales, best_products |
| `/api/shop/analytics` | 접속통계 블록 | shop_analytics |
| `/api/ads/channels` | 광고 탭 전체 | ads_by_channel, channel_detail, ads_trend |
| `/api/ads/keywords?channel=&sort=` | 네이버 키워드·플레이스 | keyword_report, place_report |
| `/api/creatives/overview?channel=` `/api/creatives/trend?channel=` | 소재 카드·추이 | creatives_overview, creative_trend |
| `/api/ga4/site` | GA4 탭 | ga4_site (+ funnel, channels, pages) |
| `/api/competitors/directory` `/api/competitors/trend` | 경쟁사 | competitor_directory, competitor_trend |
| `/api/report/weekly(.docx)?week=` `/api/report/monthly(.docx)?month=` | 리포트 | period_report |
| `/api/channels` `/api/logs?limit=` | 채널 연결 | channel_status, store.recent_logs |
| `/health` | 상태 확인 | — |

서버로 띄울 때 `DASHBOARD_PASSWORD` 가 있으면 `/login` 을 거쳐야 API 가 열린다(없으면 401).

## 7. 설정 파일

- `config/sources.yaml` — 업체 값: `client_id`, `brand`, `site_url`, `lead_gen`, `shop.platform`/`mall_id`, `competitors[]`
- `config/metrics.yaml` — `summary_cards`(카드 구성), `targets.monthly_sales`(월 목표), `category_groups`(카테고리 그룹)
- `config/secrets.env` — 로컬 실행용 키(gitignore). 견본은 `secrets.env.example`. 운영은 GitHub Secrets 에 같은 이름으로.
- `CAFE24_OPS_MODE` = `live` | `demo`

## 8. 새로 추가할 때

**화면에 그래프·표 하나 추가**
1. `etl/breakdown.py` 에 계산 추가(기존 API 응답에 필드를 얹는 것이 가장 간단하다)
2. `dashboard/index.html` 에 `<div class="panel">` + `<canvas>`/`<table>` 추가, `load*()` 에서 `mk()`(차트)·`tbl()`(표)로 그린다
3. 새 API 경로를 만들었다면 `scripts/export_static.py` 스냅샷과 `snapGet()` 에 추가
4. 데모로 확인: `run_all.py --mode demo` → `export_static.py` → Playwright 캡처

**지표 하나 추가**: 더할 수 있는 값이면 `ADDITIVE` 에, 비율이면 `derive()` 에. 화면 표기는 `index.html` 의 `UNIT`·`LABEL`.

**광고 채널 추가**
1. `clients/ads_<채널>.py`: `REQUIRED_ENV`, `is_configured()`, 하루치 5지표를 돌려주는 `daily(d)`
2. `collectors/ads.py` 의 jobs 에 추가, `active_channels()` 에 추가
3. `collectors/__init__.py` 의 `AD_CHANNELS`(채널 연결 카드), `breakdown.CHANNEL_LABEL`(화면 이름)
4. `config/secrets.env.example`, `daily-collect.yml`·`channel-check.yml` 의 env, `scripts/smoke_live.py`
5. `collectors/demo.py` 에 데모 값, `tests/test_pipeline.py` 갱신

**탭 추가**: `<nav>` 버튼(`data-tab`) + `<section id="tab-…">` + `load…()` 를 `loadAll()` 에 추가.

**API 응답 모양을 모를 때**: 추측으로 쓰지 말고 진단 스크립트를 먼저 만든다(`scripts/*_probe.py` + `probe.yml`). 키 이름·목록 모양만 출력하고 금액은 찍지 않는다. 카페24 통계·카카오·구글 모두 문서와 실제 응답이 달랐다.
