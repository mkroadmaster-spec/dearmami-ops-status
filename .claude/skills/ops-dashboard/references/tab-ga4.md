# 탭 4 · 유입·구매 경로 (GA4) (`#ga4`)

방문자가 어디서 들어와 어느 단계에서 빠지는지 본다. **GA4 를 연결해야 채워진다.** 연결 전에는 카드에 "미연결"이 나온다(카페24 어드민 탭의 방문자 지표는 카페24 접속통계로 대신 채워진다).

화면 코드: `section#tab-ga4` + `loadGa4()` · API: `/api/ga4/site` → `breakdown.ga4_site()`
수집: `clients/ga4.py`(GA4 Data API, 서비스 계정) → `collectors/ga4.py` → facts source 4개: `ga4`(일별 합계) · `ga4_channel`(매체별) · `ga4_page`(페이지별) · `ga4_event`(이벤트 건수)
필요한 키: `GA4_PROPERTY_ID`(숫자만), `GOOGLE_APPLICATION_CREDENTIALS_JSON`(서비스 계정 JSON 전체) — 안내는 `docs/GA4-SETUP.md`

---

## 1. KPI 카드

캡처: `screens/ga4-01-kpi-cards.png`

- **보여주는 것**: 방문자 · 세션 · 페이지뷰 · 평균 체류시간 · 신규 방문 · 재방문 · 재방문율 · GA4 전환 (비교기간 대비)
- **계산**: 평균 체류시간은 날짜별 평균을 평균 내지 않는다. `평균 × 세션`을 총합으로 보관했다가(`session_sec_total`) 기간 세션 합으로 나눈다. 재방문율 = 재방문 ÷ 방문자.

## 2. 구매 퍼널 · 단계별 이탈 / 신규 vs 재방문

캡처: `screens/ga4-02-funnel_new-vs-returning.png`

- **구매 퍼널 표**: 단계 · 건수 · 직전 단계 대비 · 첫 단계 대비 · 이탈
  - 단계(`clients/ga4.py: FUNNEL_STEPS`): 페이지 조회(`page_view`) → 상품 탐색(`view_item`) → 바로구매 클릭(`click_buy_now`, **분기**) → 장바구니 담기(`add_to_cart`) → 장바구니 확인(`view_cart`) → 구매하기 클릭(`begin_checkout`) → 결제 완료(`purchase`)
  - **병목** = 직전 단계 대비 통과율이 가장 낮은 단계(빨간 태그, 행 강조). '바로구매 클릭'은 장바구니를 거치지 않는 분기라 병목 판정에서 뺀다.
  - 건수가 0 인 단계가 있으면 "GA4 이벤트 미설치 가능성" 문구가 붙는다.
- **신규 vs 재방문**: 도넛.
- **출처**: `breakdown.ga4_funnel()` (facts `ga4_event` 의 `event_count`)
- **주의 — 반드시 사용자에게 설명할 것**: 이 퍼널은 **한 사람의 이동 경로가 아니라 단계별 이벤트 건수**다. "A 를 본 사람이 B 로 갔다"는 추적은 GA4 → BigQuery 내보내기가 있어야 가능하다. 화면에도 이 문구가 적혀 있다.

## 3. 매체별 유입·전환 / 인기 페이지 TOP

캡처: `screens/ga4-03-channels_pages.png`

- **매체별 유입·전환**: 매체(source / medium) · 채널 · 세션 · 사용자 · 전환 · CVR
  - '채널' 열은 `channel_of()` 가 source/medium 을 광고 채널로 묶은 것(facebook·instagram → Meta, naver → 네이버 등). 이 매핑이 광고 탭의 'GA4 전환' 열에도 쓰인다.
- **인기 페이지 TOP**: 페이지 경로 · 조회 · 사용자
- **주의**: 전환이 전부 0 이면 GA4 에서 '핵심 이벤트(전환)'로 `purchase` 를 표시하지 않은 것이다.

---

## GA4 가 없을 때

디어마미처럼 GA4 를 연결하지 않아도 대시보드는 동작한다. 이 탭만 비고, 방문자·신규/재방문은 카페24 접속통계 값으로 대체된다(`aggregate.kpis_from_facts()` — `visitors_source` 0 = 카페24, 1 = GA4). 사용자가 "방문자 숫자가 GA4 와 다르다"고 하면 정의가 다른 것이지 오류가 아니다.
