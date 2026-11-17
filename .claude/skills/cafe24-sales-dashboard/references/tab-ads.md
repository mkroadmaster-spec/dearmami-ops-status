# 탭 2 · 광고 (`#ads`)

광고 채널 전체와 채널별 성과를 본다: 어디에 얼마 썼고, 얼마 벌었는지.

전체 배치: `screens/ads-00-full.png` · 화면 코드: `section#tab-ads` + `loadAds()`
API: `/api/ads/channels`, `/api/summary`

## 광고 데이터의 구조 (먼저 알아둘 것)

- 모든 광고 채널은 facts 테이블의 **`source='ads'`** 한 곳에, `dims.channel` 로 구분되어 들어간다.
- 채널마다 지표는 5개로 통일한다: `ad_cost`(광고비) · `impressions`(노출) · `clicks`(클릭) · `conversions`(전환) · `ad_revenue`(광고 매출).
- 채널 키와 화면 이름(`breakdown.CHANNEL_LABEL`): `meta`→Meta, `naver_powerlink`→네이버 파워링크, `naver_place`→네이버 플레이스, `google`→Google, `kakao`→카카오, `criteo`→크리테오, `gfa`→네이버 GFA, `mobon`→모비온.
- 네이버 검색광고는 하나의 계정이지만 캠페인 유형(`campaignTp`)으로 **파워링크/플레이스를 자동 분리**해 두 채널로 저장한다.
- 수집기는 `cafe24_ops/collectors/ads.py` 하나다. 채널별 클라이언트(`clients/ads_*.py`)를 차례로 부르고, 키가 없는 채널은 건너뛴다. 한 채널이 실패해도 나머지는 저장한다(부분 실패).
- API 가 없는 채널(GFA·모비온)은 CSV 를 `data/manual/<채널>/` 에 올리면 같은 형식으로 들어간다(`clients/manual_csv.py`, `docs/CSV-CHANNELS.md`).

---

## 1. KPI 카드

캡처: `screens/ads-01-kpi-cards.png`

- **보여주는 것**: 총 광고비 · 광고 매출 · ROAS · 노출량 · 클릭수 · 전환율 · CTR · CPC · 매출대비 광고비 (각각 비교기간 대비)
- **계산** (`aggregate.derive()`):
  - ROAS = 광고 매출 ÷ 광고비 (화면은 `3.58x`)
  - 전환율(CVR) = 전환 ÷ 클릭 × 100
  - CTR = 클릭 ÷ 노출 × 100, CPC = 광고비 ÷ 클릭, CPA = 광고비 ÷ 전환
  - 매출대비 광고비 = 광고비 ÷ **전체 매출**(카페24) × 100
- **리드젠 업체**(`config/sources.yaml` 의 `lead_gen: true`): ROAS 대신 전환(결과)·CPA·CVR 중심 카드로 바뀐다.
- **주의**: 광고비·CPC·CPA·매출대비 광고비는 오르면 빨강(나쁨)으로 표시한다.

## 2. 채널별 예산 비율 · 채널별 성과 요약

캡처: `screens/ads-02-budget_summary.png`

- **예산 비율**: 선택 기간 광고비에서 각 채널이 차지하는 비중 막대 + 금액
- **성과 요약 표**: 채널 · 광고비 · 비교 대비 · 노출 · 클릭 · CTR · CPC · 전환(결과) · 비교 대비 · CPA · CVR · GA4 전환 · 광고매출 · ROAS
- **출처**: `/api/ads/channels` 의 `channels` → `breakdown.ads_by_channel()`
- **'GA4 전환' 열**: GA4 의 매체(source/medium)를 광고 채널로 매핑해 넣는다(`clients/ga4.py: channel_of()`). 광고 플랫폼이 보고한 전환과 GA4 가 본 전환을 비교하는 용도다. GA4 가 없으면 `—`.

## 3. 채널별 상세 · 흐름

캡처: `screens/ads-03-channel-detail-flow.png` (채널 하나의 칸. 채널 수만큼 반복된다)

- **보여주는 것** — 채널마다 한 칸:
  - 제목 + 예산 비중 태그
  - 미니 카드 6개: 총 광고비 · 광고 매출 · ROAS · 노출량 · 클릭수 · 전환율 (비교기간 대비)
  - **최근 30일 흐름 — 작은 그래프 6개**(3열): 광고비 · 광고 매출 · ROAS · 클릭수 · 전환수 · 전환율
    - 그래프마다 머리에 **30일 합계**(ROAS·전환율은 합계로 다시 계산한 기간 전체 값)와 **▲▼ = 최근 15일 vs 그 앞 15일**
    - 점선 = 일 평균. 한 그래프에 마우스를 올리면 같은 채널의 나머지 다섯 그래프도 **같은 날짜**를 가리킨다.
    - **회색 띠 = 수집 누락일.** 그 날 데이터 행이 없다는 뜻이다(0원이 아니다). 안내 태그에 날짜가 나온다.
- **왜 이렇게 생겼나**: 광고비·ROAS·클릭수는 단위가 달라 한 그래프에 겹치면 눈금이 섞인다. 그래서 지표마다 축이 하나인 작은 그래프로 나누고, 날짜만 같이 움직이게 했다. 색은 채널 색 하나로 통일한다(색 = 채널).
- **출처**: `/api/ads/channels` 의 `detail` → `breakdown.channel_detail()`. `trend` 안에 `dates`(빈 날 포함 연속 30일), `ad_cost`, `ad_revenue`, `roas`, `ad_clicks`, `ad_conversions`, `cvr`, `missing_dates`.
  - 그 날짜에 채널 행이 없으면 값은 `null` 이다. **0 으로 채우지 않는다** — 누락을 '0원'으로 그리면 급락처럼 보인다.
- **주의**: 흐름 그래프는 기간 선택과 무관하게 **선택기간 끝 날짜 기준 최근 30일**이다. 채널 순서는 광고비가 큰 순.
- **그래프를 더 넣고 싶을 때** (예: CPC 흐름): ① `channel_detail()` 의 `trend` 에 배열 추가 ② `loadAds()` 의 `TREND` 배열에 한 줄 추가 — `[키, 이름, 'bar'|'line', 대표값 함수(t, a, b), 값 표기, 축 표기]`. 캔버스·머리글·동기화는 자동으로 만들어진다.
  - `/api/ads/channels` 는 이미 스냅샷에 들어 있으므로 `export_static.py`·`snapGet()` 은 건드리지 않는다.
- 회색 띠가 보이면 → `operations.md` 의 "광고 데이터가 빠진 날 찾기".

## 4. 미연동 광고 채널 안내

캡처: `screens/ads-04-unlinked-channels.png`

- 연동하지 않은 채널에 광고를 집행 중이면, 유입은 잡히지만 광고비가 빠져 **전체 ROAS 가 실제보다 높게** 보인다는 경고문이다. 업체에 미리 알려야 한다.

---

## 자주 받는 질문

- **"대시보드 ROAS 가 광고 관리자 화면과 달라요"** → 광고 매출은 각 플랫폼이 보고한 전환 매출이다. 기여 기간이 다르다: 카카오는 7일 클릭 기준(`conv_purchase_p_7d`), 크리테오는 30일(`RevenueGeneratedAllPc30d`). 관리자 화면의 기여 설정과 같은지 먼저 본다.
- **"어제 숫자가 오늘 바뀌었어요"** → 정상. 플랫폼이 전환을 뒤늦게 확정한다. 그래서 매일 수집이 **최근 3일을 다시 받는다**.
- **"특정 날 광고비가 튀어요"** → 그 채널의 관리자 화면에서 같은 날을 확인한다. 실제 집행일 수도, 플랫폼의 일괄 정산일 수도 있다. 수집 중복은 아니다(facts 는 날짜·소스·지표·dims 가 기본키라 중복 저장되지 않는다).
