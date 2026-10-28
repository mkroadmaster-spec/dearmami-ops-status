---
name: 온라인-광고
description: 온라인 광고 성과 대시보드(광고 채널 성과·ROAS·CTR·CPC·전환 + 소재/키워드 '광고 히스토리' + 경쟁사 모니터링 + 월간 브리핑 리포트)를 신규 업체에 배포/연동하거나 점검/수정할 때 사용. Meta·네이버SA(파워링크/플레이스 분리)·구글·카카오 광고 API, GA4(전환·사이트분석), 네이버 DataLab/검색(경쟁사), 구글시트(지역현황·경쟁사 소재)를 다룬다. 리드젠(자사몰 없는 상담·문의형) 업체는 '전환=구매'가 아니라 Meta '결과'(웹사이트 등록 완료/리드/문의)로 집계한다(매출/방문 운영지표는 '카페24-운영현황' 스킬). "광고만 세팅", "소재/키워드 성과", "ROAS 대시보드", "리드젠 전환/결과값", "GA4 전환 연동", "경쟁사 모니터링/인스타/광고라이브러리", "광고 히스토리", "월간 리포트/브리핑", "지역 현황" 같은 요청에 사용.
---

# 온라인 광고 (광고 · 광고 히스토리 · 경쟁사 도메인)

광고 성과를 매일 무인 수집해 **"광고" / "광고 히스토리" / "경쟁사 모니터링" / "월간 리포트" 4개 탭**으로 보여주는
무료 자동화 도메인. 매출·방문 운영지표는 별도 스킬(**카페24-운영현황**)이라, 광고만 원하는 업체는
이 스킬만으로 세팅·운영한다(자사몰 없는 업체 = `shop.platform: none` → 카페24 수집기 자동 스킵).
프로젝트 루트: `cafe24-ops-status/`(원본) 또는 업체 복제본(예: `dbrick-ads-status/`).

**리드젠(구매 없는 상담·문의형) 업체**: '전환'을 구매가 아니라 Meta '결과'(웹사이트 등록 완료/리드/문의)로 집계한다.
KPI·소재·차트·월간리포트 전반이 매출/ROAS 대신 **결과(전환)·전환당비용(CPA)·전환율(CVR)** 중심으로 구성됨.

## 이 도메인이 다루는 것 (4개 탭)

- **광고**: 채널별(Meta·**네이버 파워링크/플레이스**·구글·카카오) 광고비·**결과(전환)·CPA·CVR**·CTR·CPC·노출.
  네이버는 `campaignTp`로 파워링크(WEB_SITE)/플레이스(PLACE) **자동 분리**. **전환수는 GA4 기준으로 대체**
  (source/medium → 채널 매핑, keyEvents/conversions 중 큰 값). 선택 vs 비교기간 증감 + 채널 추이(결과 흐름).
  하단 **GA4 사이트 분석**: 방문자·세션·페이지뷰·체류·신규/재방문 + **매체별 유입·전환 표** + **인기 페이지 TOP**.
- **광고 히스토리**: 채널 탭 — **Meta 소재**(이미지 카드 + **전환(결과)·전환율·CPA**·CTR·CPC·피로도) / **네이버 검색(키워드)**
  리포트(광고비 소진 기준 정렬, 캠페인·광고그룹·노출·클릭·CTR·CPC·전환) / **네이버 플레이스**(광고그룹 단위).
- **경쟁사 모니터링**: **지정 현황 딥링크**(홈페이지·인스타·페북 광고라이브러리(active만)·구글 광고 투명성)
  + **인스타 게시물 임베드**(구글시트 `링크`만 넣으면 이미지+캡션 자동, 최근 10일) + **구글시트 소재**(메타/구글 이미지)
  + 네이버 DataLab 트렌드·검색.
- **월간 리포트**: 온라인광고 컨설턴트 관점 **월간 브리핑**(전월 vs 전전월) — 한줄요약·KPI 증감표·좋아진/아쉬운·
  매체별 비교+해석·키워드 TOP·다음달 전략 초안. **매월 1일 자동 생성**(전월 확정분)해 탭에서 확인, **Word(.docx) 다운로드**로 편집 가능.
- 하단 **온라인 인입 지역 현황**(구글시트, 서비스계정 비공개 연동) — 월간 리포트 탭에선 숨김.

**데이터 소스**: Meta Marketing API(계정+ad-level+소재 썸네일; **actions/action_values 로 결과·구매 집계**) · 네이버 검색광고 API(계정/캠페인/광고그룹/키워드 stats)
· (선택)구글/카카오 · **GA4 Data API**(전환·사이트지표·source_medium·pages·newVsReturning) · 네이버 DataLab/검색(경쟁사)
· **Google Sheets API v4**(서비스계정 — 지역현황·경쟁사 소재). **월간 리포트**는 신규 수집 없이 `facts`(ads/creative/naver_keyword)를 월 단위 집계해 생성.

## 무료 스택 (모든 도메인 공통)

| 역할 | 플랫폼 | 비고 |
|---|---|---|
| 매일 수집 | GitHub Actions | `*-daily-collect.yml` (**07:00 KST = cron "0 22 * * *"**, 전 채널) |
| 데이터 영속 | Neon Postgres | `DATABASE_URL` |
| 웹/API | Render Web Service | 무료(15분 무접속 슬립 → keepalive로 방지, 자동 재배포 on push) |

수집 → 정규화 → Neon(`facts`) → FastAPI → React. 소재/키워드/경쟁사/GA4는 KPI 합산이 아니라 `facts`를 직접 집계해 서빙.
한 수집기가 여러 `source`를 낼 수 있고(예: ga4_site→ga4_site/ga4_channel/ga4_page), 파이프라인은 수집된 소스만 `delete_facts`+upsert.

## 신규 업체 온보딩 (광고만)

1. **저장소**: repo 포크/복제. 2. **Neon** `DATABASE_URL`.
3. **광고 채널**(있는 것만 — 없으면 자동 스킵):
   - **Meta**: `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` (+ `META_APP_ID`/`META_APP_SECRET` → 실행당 1회 60일 장기토큰 자동 갱신, DB 영속).
     **리드젠 업체는 '전환=결과'**(구매 아님): `RESULT_ACTION_TYPES`(complete_registration/lead/submit_application/contact/messaging/lead_grouped)를 합산, 없을 때만 구매로 폴백. 계정마다 최적화 이벤트가 다르면 조정.
   - **네이버SA**: `NAVER_SA_API_KEY`, `NAVER_SA_SECRET_KEY`, `NAVER_SA_CUSTOMER_ID`. (파워링크/플레이스 자동 분리 + 키워드 리포트)
   - **구글/카카오**(후순위): `GOOGLE_ADS_*` / `KAKAO_ACCESS_TOKEN`,`KAKAO_AD_ACCOUNT_ID`.
4. **GA4(전환·사이트분석)**: `GA4_PROPERTY_ID`(숫자만!) + `GOOGLE_APPLICATION_CREDENTIALS_JSON`(서비스계정 키). 서비스계정 이메일을 GA4 속성 뷰어로 공유. 전환수가 0이면 GA4 "핵심 이벤트(키 이벤트)" 미설정 → 상담신청 등을 키 이벤트로 지정.
5. **경쟁사**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`(DataLab+검색 API 둘 다 사용 설정). `config/sources.yaml`의 `competitors[]`에 `name/url/insta/domain/fb_query`.
6. **구글시트(선택)**: `region_status`·`competitor_media`에 `sheet_id/gid`. 시트를 위 서비스계정 이메일에 **뷰어 공유**(GA4 키 재사용). 인스타는 시트 `링크`만으로 임베드.
7. **Render**: Blueprint → env(`DATABASE_URL`+광고/네이버/GA4/시트 키) → Deploy. **schedule은 기본 브랜치에서만 동작.**
8. **백필**: Actions `daily collect` 수동 실행(`days: 31`). 9. **검증**: `*-api-smoke.yml`(200), `/health`(ga4_creds/ga4_property 플래그).
10. **월간 리포트**: 별도 세팅 불필요(수집된 `facts` 만으로 온디맨드 생성). API `/api/report/monthly` 는 month 미지정 시 **`latest_complete_month`(KST 오늘의 전월)** 를 기본값으로 → **매월 1일이 되면 탭이 자동으로 전월 리포트를 표시**(스케줄 업로드 불필요). `*-report.yml`(workflow_dispatch)은 두 달치 집계를 로그 JSON 으로 뽑는 수동 점검용.

> **멀티테넌트 주의(같은 repo에 여러 대시보드)**: GitHub 저장소 Secrets는 **repo 전체 공유** → 업체별 `TENANT_` 접두어(예: `DBRICK_META_ACCESS_TOKEN`)로 충돌 방지, 워크플로에서 원래 이름 env로 매핑. Render env는 서비스 격리라 접두어 불필요.

### 업체별 필수 교체
`config/sources.yaml`(`shop.platform`, `ads[].account_id`, `competitors[]`, `region_status`/`competitor_media` 시트) · `render.yaml`(`services[].name`) · keepalive/smoke 워크플로의 하드코딩 도메인 · GitHub Secrets · `dashboard/index.html` `<title>`(브랜딩).

## 핵심 함정/교훈 (이 도메인)

- **GA4 전환 400 "Found duplicate metrics: conversions"** → `keyEvents`와 `conversions`는 GA4 내부 동일 지표. 한 요청에 같이 넣지 말 것. keyEvents 단독 → 실패 시 conversions 단독 폴백(`_report_with_conv_metric`). 파서는 둘 중 큰 값 사용.
- **GA4 전환이 0** → 속성에 "핵심 이벤트"가 없음(코드 아님). / `GA4_PROPERTY_ID`에 복붙 히든문자 → 숫자만. `/health`의 ga4_creds/ga4_property로 진단.
- **네이버 키워드 /stats 400** → 한 `/stats` 호출의 `ids`는 **동일 엔티티 유형**이어야 함(키워드 nkw-·광고그룹 grp- 혼합 금지) → 유형별 분리 호출. 키워드 메타(캠페인→광고그룹→키워드)는 날짜 무관 → **프로세스 캐시**(백필 시 매일 재크롤 방지).
- **구글시트 404/인식 실패** → 탭 이름 공백은 A1 표기 작은따옴표+URL인코딩. 서비스계정 있으면 비공개 Sheets API, 없으면 공개 CSV 폴백. 헤더가 첫 줄이 아니어도 되게 **헤더 줄 자동 탐지**(위 안내문/찌꺼기 skip).
- **경쟁사 광고 소재 자동수집** → FB/구글은 경쟁사 상업광고 **무료/공식 API 없음**(FB API는 정치광고만). 서버 스크래핑은 IP 차단. → **딥링크(active 필터)** + 인스타 **임베드**(`/p|reel/{code}/embed/captioned`) + 시트 이미지URL. 유료 자동은 Apify류.
- **리드젠인데 전환/구매 0** → Ads Manager '결과'(웹사이트 등록 완료 등)는 `actions[].action_type` 에 `complete_registration`/`lead`/`onsite_conversion.*` 로 옴(구매 아님). `_conversions()`가 `RESULT_ACTION_TYPES` **합산**(중복표현 offsite pixel 원시치는 제외해 과대집계 방지), 없을 때만 구매 폴백. `action_values`(매출)는 리드젠엔 없음 → ROAS 대신 CPA/CVR 지표.
- **광고 히스토리 소재별 전환만 0(계정 레벨은 정상)** → 계정 레벨(`meta_insights_to_facts`)만 결과 집계로 고치고 **소재 레벨(`meta_ad_insights_to_facts`)은 구매 조회로 남겨두면** 리드젠에서 소재별 전환이 전부 0. **두 함수 모두 `_conversions()` 로 통일**할 것. 또 ad-level 은 통합(omni/dedup) 이름 없이 픽셀 원시 이름(`offsite_conversion.fb_pixel_complete_registration` 등)만 줄 수 있어 → **결과 접미사 매칭 폴백**(`_action_sum_suffix`, 통합 이름 있으면 폴백 미진입 = 이중집계 없음).
- **소재 이미지 안 뜸** → Meta `ad-level insights`+`ads?fields=creative{thumbnail_url,image_url}`를 `source='creative'`로. **활성/최근활성만** 반환.
- **`/api/ads/overview` 422** → `cmp_from`/`cmp_to` 필수(프론트 `computeRanges`가 4값 항상 채움).
- **재수집 낡은 행 잔존** → dims 바뀌면(썸네일/키워드) 재삽입 전 `delete_facts(date, source)`.
- **Meta 토큰 만료 중단** → `META_APP_ID/SECRET`로 장기토큰 교환 후 app_kv 영속(DB 토큰 우선).
- **자사몰 없는 업체 카페24 오탐** → `shop.platform: ""/none`이면 cafe24 수집기 `NotImplementedError`로 정상 스킵.
- **경쟁사 소재 기간 필터** → 소재·포스팅은 상단 기간과 별개 **최근 10일 고정**, 종료일은 수집기준일 뒤처짐 대비 **실제 오늘**로 앵커.
- **스케줄 지연** → GitHub schedule은 정시 ±수분~최대 1시간 지연 가능(정상).
- **하루 데이터 통째 누락(날짜 어긋남)** → 러너는 UTC. 07:00 KST=전날 22:00 UTC 라 `date.today()-1`(UTC)은 KST 기준 '그저께' → 전일 누락+그전날 중복. **`yesterday()`를 반드시 KST(UTC+9)로 계산**하고 워크플로에 `TZ: Asia/Seoul`. cron 도 UTC 로 환산해 설정(07:00 KST = `0 22 * * *`).
- **지연 확정 데이터·러너 결번 대비** → 스케줄 기본 `--days 3`(최근 3일 재수집): GA4/Meta 의 24~48h 늦은 보정 반영 + 하루 실행이 빠져도 다음날 자가복구. facts 는 소스별 delete+upsert 라 중복 없음.

## 레퍼런스 (이 도메인)

**API**: `ads/summary·channels·overview(cmp_from,cmp_to 필수)·channel-trend·trend` · `ads/keywords(channel,sort=ad_cost)` ·
`creatives/overview·fatigue·trend` · `ga4/site·ga4/channels·ga4/pages` · `competitors·/trend·/naver·/directory·/media·/best-changes` · `region-status` · `report/monthly(month? 기본 latest_complete_month)·report/monthly.docx`(Word 스트리밍) · `/health`.
**핵심 파일**: `collectors/{ads,creative,naver_keyword,competitor,ga4_site}.py` · `clients/{ads_meta(RESULT_ACTION_TYPES/_conversions/_action_sum_suffix),ads_naver,ads_google,ads_kakao,ga4,naver_datalab,naver_search,region_sheet}.py`
· `etl/{ads_metrics,creative_metrics,keyword_metrics,competitor_metrics,competitor_directory,ga4_site,monthly_report}.py` · `report_docx.py`(python-docx) · `pages/{AdsPage,CreativePage,CompetitorPage,MonthlyReportPage}.tsx` + `components/{Ga4SitePanel,CreativeThumb,PeriodSelector,AdsTrendChart}`.
**로컬**: `python scripts/run_all.py --mode live --days 31` · `python scripts/monthly_report.py --a 2026-05 --b 2026-06` · `uvicorn api.main:app --reload` · `cd dashboard && npm run build` · `pytest`.
