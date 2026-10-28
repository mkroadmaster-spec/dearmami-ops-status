---
name: 매출-대시보드-구축
description: 카페24 자사몰 업체의 매출·방문·광고 운영현황 대시보드(cafe24-ops-status)를 새 업체에 처음부터 구축하거나 다른 업체로 복제할 때 사용. 실제 구축한 순서(자료 확인 → 설치 → 설정 → 저장소·클라이언트 → 수집기·ETL → API·화면 → 스크립트·워크플로·테스트 → 링크 게시 → 채널 순차 연결)를 그대로 재현하며, 각 단계의 완료 기준과 함정을 담는다. "새 업체 대시보드 만들어줘", "○○ 업체로 복제", "대시보드 틀부터 잡아줘", "채널 순서대로 연결 가이드", "데모로 먼저 보여줘", "링크로 볼 수 있게" 같은 요청에 사용. 세부 도메인은 '카페24-운영현황'(운영지표), '온라인-광고'(광고·경쟁사) 스킬을 참조.
---

# 매출 대시보드 구축 (업체 복제용 마스터 절차)

디어마미(dearmami.co.kr)를 1차 업체로 구축한 순서를 그대로 따른다. **각 단계는 "확인" 명령이 통과해야 다음으로** 간다.
레퍼런스 구현: 이 저장소(`cafe24-ops-status/`). 도메인 상세는 [`카페24-운영현황`](../카페24-운영현황/SKILL.md) · [`온라인-광고`](../온라인-광고/SKILL.md).

```
0 자료·결정 → 1 설치 → 2 업체 설정 → 3 저장소·클라이언트 → 4 수집기·ETL·브리핑
→ 5 API·화면(3탭) → 6 스크립트·워크플로·테스트 → 7 링크 게시 → 8 채널 순차 연결 → 9 무인 자동화
```

> 원칙 3가지: **① 키 없는 채널은 자동 스킵**(한 채널만 켜도 동작) **② 데모 모드로 틀을 먼저 보여준다** **③ 토큰은 DB(app_kv)가 Secret 보다 우선**.

---

## 0. 자료 확인·결정 (30분)

- 업체 사이트를 열어 **카페24 여부** 확인: 어드민 주소 `https://<몰아이디>.cafe24.com`, 또는 소스의 `cafe24.com`/`echosting` 흔적. (세션에서 사이트 접근이 막히면 담당자에게 어드민 주소를 물어본다 — 디어마미는 이 경로로 확인 대기)
- 덩어리 선택: A 운영현황 / B 광고 / C SNS. 매출 대시보드 = A(+B). C 는 별도 저장소.
- 업체가 줄 것: 카테고리명(카페24 그대로), 경쟁사명 ≤5, 집행 중 광고 채널, 담당자 1명.
- **완료 기준**: `docs/clients/<id>.md` 의 §0 체크 항목이 채워짐.

## 1. 설치 (5분)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
- Chart.js 는 `dashboard/vendor/chart.umd.js` 로 **번들**(CDN 차단 환경·오프라인 대비). 새로 받을 때: `npm pack chart.js@4.4.1` → `package/dist/chart.umd.js` 복사.
- 세션 컨테이너는 외부 API egress 가 막혀 있다 → 실수집은 로컬 PC 또는 GitHub Actions 에서.
- **완료 기준**: `.venv/bin/python -m pytest -q` 통과.

## 2. 업체 설정 (10분)

```bash
.venv/bin/python scripts/new_client.py --id <id> --brand <브랜드> --site https://... \
  --mall-id <몰아이디> --competitors "A,B" --categories "원피스:원피스,롱원피스;팬츠:팬츠,슬랙스;기타:"
```
바꾸는 곳: `config/sources.yaml`(brand·mall_id·competitors) · `config/metrics.yaml`(category_groups·요약 카드) · `render.yaml`(서비스명) · `docs/clients/<id>.md`(온보딩 기록 자동 생성).
- 데모 생성기는 **이 설정을 읽어** 업체 카테고리·상품·경쟁사 이름으로 데이터를 만든다 → 틀 확인 단계부터 업체답게 보인다.
- **완료 기준**: `run_all.py --reset --mode demo --days 60` 후 대시보드 카테고리/베스트/검색어에 업체 카테고리명.

## 3. 저장소·클라이언트 (이미 구현 — 새 채널 추가 시만)

- `cafe24_ops/store.py`: SQLite 기본, `DATABASE_URL` 있으면 Postgres. `facts`(정규화) · `kpi_daily`(집계) · `app_kv`(토큰) · `collect_log`.
- `cafe24_ops/clients/`: 채널당 파일 1개, `REQUIRED_ENV` + `is_configured()` 를 반드시 둔다.
- 카페24 토큰은 **`Cafe24Client.from_store(store)` 만** 사용 — refresh 회전분을 갱신 순간 DB 에 되쓴다. 회귀 테스트 `tests/test_cafe24_token_rotation.py`.
- **새 채널 추가 절차**: `clients/<ch>.py` → `collectors/<ch>.py` 또는 `collectors/ads.py` 의 jobs → `collectors/__init__.py` REGISTRY/AD_CHANNELS 등록 → `secrets.env.example` · `daily-collect.yml` env · `smoke_live.py` 항목 → `tests/test_pipeline.py` 기대 소스 집합.

## 4. 수집기·ETL·브리핑 (이미 구현)

- 수집기 7개 → facts source 10개: `cafe24` · `cafe24_analytics`(9블록) · `ga4`→`ga4/ga4_channel/ga4_page` · `ads`(채널별) · `creative`(Meta 소재) · `naver_keyword`→`naver_keyword/naver_place` · `competitor`. 한 수집기가 여러 source 를 내면 `Collector.sources` 에 선언(재수집 삭제 대상).
- 파이프라인 `pipeline.run_day`: live=설정된 채널만, demo=생성기. 성공 소스는 `delete_facts`+upsert, **부분 실패는 upsert 만**(기존 정상 데이터 보존), 전부 실패면 예외(빈 결과로 덮지 않음).
- 날짜는 **KST** (`pipeline.yesterday()`), 러너는 UTC.
- 집계 `etl/aggregate.py`: 합산 가능한 지표만 합산 후 파생(객단가·전환율·ROAS·CTR·CPC·CPA·CVR·체류시간)을 **재계산**(평균 체류는 총합으로 보관). 방문자는 GA4 우선, 없으면 카페24 통계 '방문'(정의 다름 → UI 에 출처 표기).
- `etl/breakdown.py`: 기간비교(전일/전주/전년) · 채널별 광고(+GA4 전환 매핑) · 카테고리/베스트 · **접속통계 9블록**(`shop_analytics`: 방문·조회→담기→주문·담기율 경고·상품별 판매·검색어·도메인·광고채널·페이지·회원/비회원) · GA4 사이트/매체/페이지 · **소재 개요+피로도**(최근 7일 vs 초반 7일 CTR 하락, 빈도) · 키워드/플레이스 리포트 · 경쟁사.
- `etl/period_report.py`: **기간 무관 코어 `period_report_data`** ← 주간(월~일 vs 전주, `WEEK_MIN_VIEWS=50`, `latest_complete_week` 는 데이터 있는 완결 주로 폴백) · 월간(전월 vs 전전월, `MONTH_MIN_VIEWS=200`). 문구는 `prev_word` 로만. `missing_dates` 를 먼저 볼 것.
- `report_docx.py`: 리포트 데이터 → Word (python-docx). 섹션 번호는 그려지는 섹션만 순서대로.
- `alerts.py`: 전일·전주·전년, 7일 평균 대비 ±30% 급등락, ROAS<200%, 수집 실패 채널.

## 5. API·화면 (이미 구현) — keek 대시보드 스크린샷 기준으로 동일 구성 (2026-10-28 재구성)

- `api/main.py`: `/health` `/api/config` `/api/dates` `/api/channels` `/api/summary` `/api/period-comparison` `/api/daily` `/api/digest` `/api/breakdown` `/api/shop/analytics` `/api/ads/channels` `/api/ads/keywords(channel,sort)` `/api/creatives/overview|trend` `/api/ga4/site` `/api/competitors/trend` `/api/report/weekly(.docx)(week)` `/api/report/monthly(.docx)(month)` `/api/logs`. 요약은 **선택 기간 합계 + 직전 동일 길이 비교**.
- 공통 UI(keek): 네이비 헤더 + **조회일** 선택 → 탭 → **오늘의 브리핑**(이모지 요약 줄 · 한 문장 · 4박스: 핵심지표/7일 평균 급등락/이상치·신규 등장/광고 지표, 접기) → **기간 선택**(어제·최근 7/14/30일·직접 + 비교: 직전 기간·전주/전월/전년 동기간, 선택·비교기간 표시) → 파란 상단선 KPI 카드. 모든 데이터 API 는 `cmp_from/cmp_to` 를 받는다. ROAS 는 `x` 배수 표기.
- `dashboard/index.html` 단일 파일, 8탭(해시 라우팅 `#ops|ads|history|ga4|comp|weekly|monthly|channels`):
  1. **카페24 어드민**: KPI 카드 → 핵심 지표 기간 비교(전일/전주/전년) → 일별 매출 추이(+누적 매출 vs 목표 페이스, `metrics.yaml targets.monthly_sales`) → 신규 vs 재구매 매출(누적 영역) · 광고비 vs 비광고 매출 → 디바이스 도넛+상세 → 방문자 상세 타일 · 신규회원(API 미제공) → 방문자 추이(전체/신규/재방문) → 카테고리 TOP10 · 베스트 TOP5 → **접속통계**(상품별 조회→담기→주문(인라인 바), 검색어/도메인/광고채널(비중·비교 대비·신규★), 담기율 경고, 회원/비회원, 페이지뷰) → 일별 운영 데이터(14일) → 세부 구성 칩
  2. **광고**: KPI(총 광고비·광고 매출·ROAS·노출량·클릭수·전환율·CTR·CPC·매출대비; 리드젠 `lead_gen: true`) → **채널별 예산 비율 바** → 채널별 성과 요약표(+GA4 전환) → **채널별 상세·흐름**(채널마다 6 미니카드 + 최근 30일 광고비 막대·ROAS 선) → 미연동 채널 안내
  3. **광고 히스토리**: 채널 서브탭. Meta 소재(KPI 6: 라이브 소재·광고비·총 전환·전환당 비용·평균 CTR·전환율 → 상위 5 CTR 추이 → 소재 카드(세로 이미지, 전환·전환율·전환당 비용·CTR·CPC·비용·ROAS·빈도·피로도) 정렬 전환/CTR/CVR/비용) / 네이버 검색(KPI 6 + 키워드 리포트 정렬 광고비/클릭/노출/전환) / 네이버 플레이스(광고그룹)
  4. **유입·구매 경로(GA4)**: 사이트 KPI 8 → **구매 퍼널·단계별 이탈**(페이지 조회→상품 탐색→바로구매 클릭(분기)→장바구니 담기→장바구니 확인→구매하기 클릭→결제 완료, 직전/첫 단계 대비·이탈, 병목 강조) → 신규 vs 재방문 → 매체별 유입·전환 → 인기 페이지
  5. **경쟁사 모니터링**: 지정 현황 딥링크(홈페이지·인스타·FB 광고라이브러리 active·구글 광고 투명성, `sources.yaml competitors[]` 객체) → 네이버 데이터랩 트렌드
  6. **주간 리포트** / 7. **월간 리포트**: 제목 "A주 → B주 성과 비교", 한 문장 요약, 이전/다음, Word — **01** 한 장 요약·계정 전체 **02** 좋아진 것·아쉬운 것(문장) **03** 매체별 비교+해석 **04** 구매 퍼널·단계별 이탈(GA4) **05** 장바구니 담기 퍼널 4타일 **06** 베스트(비중·순위 변동) **07** 고객 구성(신규/재구매 매출·회원/비회원 객단가) **08** 유입 검색어(비중·전주·신규★) **09** 네이버 키워드 흐름+코멘트 **10** 핵심 인사이트 & 다음 전략(규칙 기반 초안 4개)
  8. **채널 연결**(이 구축의 추가 장점): 11개 채널 카드(필요 env 체크·마지막 수집 상태·가이드) + 수집 로그
- 차트 규칙(dataviz): 범주색 고정 순서(파랑·주황·초록·노랑·분홍), 막대 ≤24px·상단 4px 라운드, 선 2px, 단일 축, 2개 이상 시리즈만 범례, 다크 모드 토큰.
- SQLite 는 `check_same_thread=False` + RLock (FastAPI 스레드풀).
- **완료 기준**: 전 엔드포인트 200 + Playwright 로 5탭 스크린샷(라이트/다크/모바일 400px 가로 넘침 없음, 콘솔 오류 0) + `.docx` 생성.

## 6. 스크립트·워크플로·테스트 (이미 구현)

| 파일 | 용도 |
|---|---|
| `scripts/run_all.py` | `--mode demo/live --days N --skip ... --reset --notify` |
| `scripts/cafe24_auth.py` | `--authorize` → `--code`(DB 저장, scope 누락 경고) · `--status` · `--reset` |
| `scripts/smoke_live.py --check` | 설정된 채널만 실제 1회 호출해 인증 검증 |
| `scripts/notify.py` | 브리핑 Slack 전송 |
| `scripts/dev.sh` | secrets.env 없으면 복사 → 데모 생성 → uvicorn |
| `scripts/export_static.py [--artifact]` | API 스냅샷+Chart.js 내장 정적 HTML (서버 없이 링크로) |
| `scripts/new_client.py` | 업체 전환 |
| `scripts/weekly_report.py [--monthly]` | 리포트 .docx 파일 생성 (CI 아티팩트) |
| `.github/workflows/daily-collect.yml` | 07:00 KST(cron `0 22 * * *`), `--days 3` 자가치유, Secrets 없는 채널 스킵 |
| `cafe24-weekly-report.yml` | 월 08:25 KST: 지난주 8일 보정 수집 + .docx 아티팩트(9시 전 수령 가능) |
| `cafe24-authorize-url.yml` / `cafe24-token-fast.yml` / `cafe24-token-reset.yml` | 토큰 발급(1분 만료 → 사람이 직접) / 리셋 |
| `api-smoke.yml` | 배포 URL 전 엔드포인트 200 + keepalive |
| `render.yaml` | Render Blueprint, `buildFilter.paths` 필수 |

- **완료 기준**: `pytest` 통과, `run_all.py --mode live`(키 없음) 가 전부 skip 로 끝나고 데모 facts 가 보존됨.

## 7. 링크 게시 (5분)

```bash
.venv/bin/python scripts/export_static.py --artifact   # dist/dashboard-static.html
```
- 세션 서버는 외부 접근 불가 → **정적 스냅샷**을 Artifact 로 게시(같은 파일 경로로 재게시하면 URL 유지). 프리셋 7/14/30일만 동작, 사용자 지정 기간은 숨김.
- 상시 실시간 링크가 필요하면 9단계(Render).
- **완료 기준**: 링크에서 3탭이 열리고 상단 배지가 데모/LIVE 를 정확히 표시.

## 8. 채널 순차 연결 — 쉬운 것부터 (각 5~15분)

가이드 본문은 [`docs/SETUP-GUIDE.md`](../../../docs/SETUP-GUIDE.md). 요약:

| STEP | 채널 | 핵심 | 확인 |
|---|---|---|---|
| 1 | 카페24 Admin + 통계 | 앱 생성 → **scope 7개 전부** → Redirect `https://localhost` → `cafe24_auth.py --authorize`→`--code`(1분) | `smoke_live.py --check` ✓ → `run_all.py --reset --mode live --days 14` → 배지 LIVE |
| 2 | GA4 | Data API 사용설정 + 서비스계정 뷰어 + 속성 ID 숫자만 | 방문자·전환율 카드 채워짐 |
| 3 | Meta | **시스템 사용자 토큰(만료 없음)** ads_read, `act_` 숫자 | 광고 탭 Meta 행 |
| 4 | 네이버 SA | 콘솔 복사 3종 (가장 쉬움) | 파워링크/플레이스 자동 분리 |
| 5 | 네이버 데이터랩 | Client ID/Secret + competitors | 경쟁사 트렌드 |
| 6~7 | 카카오·Google Ads | 후순위(토큰 단기 만료·개발자 토큰 승인) | 광고 탭 행 |
| 8 | Slack | Webhook | `notify.py` 도착, 실패 채널 매일 알림 |

각 단계 후 **채널 연결 탭 카드가 녹색**이면 완료. 실 키 첫 수집 시 응답 필드 1회 검증(문서 기준 작성).

## 9. 무인 자동화 (1시간)

1. GitHub 저장소(업체당 1개, private) 푸시 — 워크플로는 main 에 있어야 schedule 동작
2. Neon `DATABASE_URL` → GitHub Secrets (러너 초기화 → 외부 DB 없으면 카페24 회전 토큰 유실)
3. 채널 Secrets 를 `secrets.env` 와 같은 이름으로 등록
4. 카페24 토큰을 Neon 에: 로컬 `DATABASE_URL=... cafe24_auth.py` 또는 Actions `authorize url`→`token fast`
5. Actions `ops daily collect` (`days: 30`, `reset: true` 최초 1회)
6. Render Blueprint → env(`DATABASE_URL`+키) → `https://<서비스명>.onrender.com`
7. `api smoke` 로 200 확인, Variables `DASHBOARD_URL` 등록(keepalive)

---

## 반드시 피할 사고 (keek 실제 사례 + 이번 구축에서 겪은 것)

- 카페24 refresh 회전분 미저장 → 다음 실행 `invalid_grant`. `from_store` 외 금지.
- scope 축소 재인증 → 오류 없이 지표가 `—`. 7개 전부. `cafe24_auth.py --status` 로 확인.
- Meta 60일 사용자 토큰 → 조용히 36일 결측. 시스템 사용자 + Slack.
- DB 토큰이 Secret 보다 우선 → 키 재발급 후 `--reset`/`cafe24 token reset`.
- 러너 UTC → 하루 통째 누락. KST 계산 + `--days 3`.
- SQLite 를 FastAPI 스레드에서 공유 → `check_same_thread=False` + 락 (이번 구축에서 500 발생).
- CDN 차단 환경 → Chart.js 번들. 세션에서 업체 사이트 접근 불가 → 담당자에게 어드민 주소 확인.
- Render 무료 빌드 분 → `buildFilter.paths`. 신규가입수는 카페24 API 로 불가(`—` 정상).

## 업체 전환 체크리스트

```
[ ] 저장소 복제 (업체당 1개)
[ ] scripts/new_client.py --id --brand --site --mall-id --competitors --categories
[ ] run_all.py --reset --mode demo --days 60 → dev.sh → 3탭 확인 → export_static.py --artifact → 링크 공유
[ ] docs/clients/<id>.md 담당자 발급 표를 업체에 전달
[ ] STEP 1 카페24 → smoke ✓ → --reset --mode live
[ ] STEP 2~8 순서대로, 매 단계 채널 연결 탭 녹색 확인
[ ] STEP 9 Neon + Secrets + Actions 백필 + Render
[ ] 1주일 뒤 collect_log 에 fail/partial 없는지, 브리핑 '특이사항 없음' 확인
```
