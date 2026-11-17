# 탭 3 · 광고 히스토리 (`#history`)

광고 **소재(이미지) 단위**와 **키워드 단위** 성과를 본다. 위쪽 채널 버튼으로 5개 화면을 오간다.

화면 코드: `section#tab-history`, `setHist()`, `loadHistory()`, `loadCreatives()`, `renderCreatives()`, `loadKeywords()`

| 버튼 | 캡처 | facts source | 수집기 |
|---|---|---|---|
| Meta 소재 | `screens/hist-01-meta-creatives.png` | `creative` | `collectors/creative.py` |
| 구글 소재 | `screens/hist-02-google-creatives.png` | `google_creative` | `collectors/google_creative.py` |
| 카카오 소재 | `screens/hist-03-kakao-creatives.png` | `kakao_creative` | `collectors/kakao_creative.py` |
| 네이버 검색(키워드) | `screens/hist-04-naver-keywords.png` | `naver_keyword` | `collectors/naver_keyword.py` |
| 네이버 플레이스 | `screens/hist-05-naver-place.png` | `naver_place` | `collectors/naver_keyword.py` |

처음 열 때 Meta 소재가 비어 있으면 소재가 있는 채널(구글 → 카카오)을 자동으로 먼저 보여준다(`HIST_AUTO`).

---

## 1~3. 소재 화면 (Meta · 구글 · 카카오 공통)

세 채널이 같은 화면 틀을 쓴다. API 에 `channel=meta|google|kakao` 만 다르다.

- **KPI 카드 6개**: 라이브 소재 수(+ 최고 성과 소재 이름) · 광고비 · 총 전환(결과) · 전환당 비용 · 평균 CTR · 전환율
- **소재별 CTR 추이**: 광고비 상위 5개 소재의 날짜별 CTR 선. CTR 이 내려가고 빈도가 올라가면 소재 피로다.
- **소재 카드**: 소재 이미지 + 이름 + `채널 · 캠페인 · 광고 유형` + **피로도 태그** + 지표 표
  - 지표: 전환(결과) · 전환율 · 전환당 비용 · CTR · CPC · 비용 · ROAS · (Meta 만) 빈도 · CTR 초반→최근
  - 정렬 버튼: 전환(결과) / CTR / CVR / 비용 (화면에서 정렬)
- **출처**: `/api/creatives/overview?channel=`, `/api/creatives/trend?channel=` → `breakdown.creatives_overview()`, `creative_trend()`
- **피로도 판정** (`creatives_overview()`):
  - CTR 하락률 = (기간 초반 7일 CTR − 최근 7일 CTR) ÷ 초반 CTR
  - `높음`: 하락률 ≥ 25% 또는 평균 빈도 ≥ 3.5 / `주의`: 하락률 ≥ 10% 또는 빈도 ≥ 2.5 / 그 외 `정상`
  - 빈도 지표가 없는 채널(구글·카카오)은 CTR 하락만으로 판정한다.
- **이미지**: 수집할 때 `dims.thumbnail_url` 에 주소를 저장하고 화면은 `<img referrerpolicy="no-referrer">` 로 불러온다. 이미지가 없으면 회색 칸에 광고 유형 이름이 나온다. 구글·카카오 카드는 정사각형(`.cr.g`), Meta 는 세로형.

### 채널별 수집 방법과 함정

**Meta** (`clients/ads_meta.py`)
- 광고 단위 인사이트 + 소재 썸네일. 활성 또는 최근 활성 광고만 이미지가 있다.
- 토큰은 **시스템 사용자 토큰(만료 없음)** 을 쓴다. 일반 사용자 토큰은 60일 뒤 조용히 끊긴다.

**구글** (`clients/ads_google.py: creative_rows()`, `creative_thumbnails()`)
- GAQL 로 `ad_group_ad`(일반 광고)와 `asset_group`(실적 최대화 — ad_id 를 `ag<번호>` 로 저장) 성과를 받는다.
- 이미지는 `ad_group_ad_asset_view`, `asset_group_asset` 에서 한 번에 받아 매핑한다. 유튜브 영상 소재는 `https://i.ytimg.com/vi/<id>/hqdefault.jpg` 를 썸네일로 쓴다.
- 개발자 토큰이 Explorer 등급이면 하루 약 2,880회 제한이다 → **30일 단위로 한 번에 받아 캐시**한다(날짜마다 호출하지 않는다).

**카카오모먼트** (`clients/ads_kakao.py`, `collectors/kakao_creative.py`) — 가장 까다롭다
- 리포트 API 제한이 매우 엄격하다: 문서상 5초에 1회지만 실제로는 더 자주 429 가 난다. `_get()` 이 429 를 만나면 쉬었다 재시도하고 이후 호출 간격을 자동으로 늘린다.
- 광고계정 리포트에 소재 단위(`level=CREATIVE`)는 없다. **`/creatives/report?creativeId=a,b,c`** 로만 소재별 일자 성과를 받을 수 있다.
- 한 번에 보낼 수 있는 ID 수가 문서에 없고 실제로는 3개 안팎이다(31일 구간 기준). `report_rows()` 가 400(78003)이 나면 묶음을 절반씩 줄여 가며 찾는다.
- 그래서 **31일 구간을 한 번에** 처리한다: ① 광고그룹 상세의 집행기간(`schedule.beginDate/endDate`)으로 그 구간에 돌았을 광고그룹만 추림 → ② 그 캠페인만 캠페인 리포트 → ③ 노출 있던 캠페인의 소재만 소재 리포트.
- 광고그룹 집행기간과 소재 이미지·형식은 DB(`app_kv` 의 `kakao_adgroup_sched`, `kakao_creative_meta`)에 캐시해 매일 다시 부르지 않는다.
- 이미지 주소가 `//t1.kakaocdn.net/...` 처럼 프로토콜 없이 온다 → `https:` 를 붙인다(`creative_thumb()`).
- 하루 비용 상위 40개 소재만 저장한다(DB 용량).
- 680일 백필에 약 3.5시간 걸렸다.

---

## 4. 네이버 검색(키워드)

캡처: `screens/hist-04-naver-keywords.png`

- **KPI 카드 6개**: 키워드 수 · 광고비 소진 · 노출수 · 클릭수 · 평균 CTR · 평균 CPC
- **키워드 리포트 표**: 키워드 · 캠페인·광고그룹 · 광고비 소진 · 노출 · 클릭 · CTR · CPC · 전환 · ROAS
- **정렬 버튼**: 광고비 / 클릭 / 노출 / 전환 — **화면에서 정렬한다**(정적 페이지에는 광고비순 한 벌만 들어 있다).
- **출처**: `/api/ads/keywords?channel=naver_powerlink` → `breakdown.keyword_report()` (상위 300)
- **수집** (`clients/ads_naver.py`): HMAC 서명 API. 캠페인 → 광고그룹 → 키워드 목록을 받고 `/stats` 로 키워드별 일자 성과를 받는다.
  - 목록(캠페인·광고그룹·키워드)은 **실행당 한 번만** 조회해 모듈 캐시에 둔다. 날짜마다 다시 받으면 백필이 하루 3분씩 걸린다.
  - 키워드가 수천 개라 매일 전부 조회하면 느리다 → **그 달에 노출이 있던 키워드만** 먼저 가려내고(`active_keywords()`, 달마다 1회) 그것만 일별로 조회한다. 하루 약 9초.
  - `/stats` 의 `ids` 는 같은 종류만(캠페인·광고그룹·키워드를 섞으면 안 된다), 100개씩.
  - 하루 비용 상위 60개 키워드만, 0 인 지표는 저장하지 않는다(DB 용량). 집계할 때 없는 지표는 0 으로 본다.

## 5. 네이버 플레이스

캡처: `screens/hist-05-naver-place.png`

- **보여주는 것**: 플레이스 캠페인의 광고그룹별 노출·클릭·CTR·CPC·광고비·전환·ROAS
- **출처**: `/api/ads/keywords?channel=naver_place` → `breakdown.place_report()`
- 플레이스 캠페인이 없으면 "플레이스 캠페인 없음 또는 미연결"이 나온다(정상).

---

## 소재 채널을 하나 더 붙일 때 (예: 크리테오 소재)

1. `clients/ads_<채널>.py` 에 소재별 일자 성과 + 썸네일을 받는 함수 추가
2. `collectors/<채널>_creative.py` 작성 — dims 는 `ad_id, ad_name, campaign, adset, ad_type, thumbnail_url` 로 맞춘다
3. `collectors/__init__.py` 의 REGISTRY 에 등록, `collectors/demo.py` 에 데모 생성기 추가
4. `breakdown.CREATIVE_SOURCES` 에 `"<채널>": "<source>"` 추가
5. `export_static.py` 에 스냅샷 키(접두사) 추가, `index.html` 의 `CR_CHANNELS`, `snapGet()` 접두사 표, 채널 버튼, `CHN` 라벨에 추가
6. `tests/test_pipeline.py` 의 기대 소스 집합에 추가
