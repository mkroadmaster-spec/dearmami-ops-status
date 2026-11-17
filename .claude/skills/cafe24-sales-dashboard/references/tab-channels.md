# 탭 8 · 채널 연결 (`#channels`)

어떤 데이터 소스가 연결됐고 마지막 수집이 어땠는지 보는 **점검 화면**이다. "데이터가 안 들어와요"라는 말을 들으면 이 탭부터 본다.

화면 코드: `section#tab-channels` + `loadChannels()` · API: `/api/channels`, `/api/logs`
코드: `cafe24_ops/collectors/__init__.py: channel_status()` — 수집기 REGISTRY 와 광고 채널 목록(`AD_CHANNELS`), CSV 채널을 합쳐 카드를 만든다.

## 1. 채널 카드

캡처: `screens/channels-01-cards.png`

- **위 안내 상자**: 연결 순서(키 입력 → 확인 → 수집 → 카드가 녹색이면 완료)
- **카드 한 장 = 채널 하나**. 카드에 있는 것:
  - 상태 점 + 채널 이름 + `STEP n`(연결 권장 순서)
  - 필요한 환경변수 목록 — 채워진 것은 ●, 비어 있으면 ○, `(선택)` 표시는 없어도 되는 값
  - 마지막 수집 상태 한 줄
  - 안내 문서 위치 + 이 채널이 채우는 탭
- **상태 색**: 녹색 = 키가 있고 마지막 수집 성공 / 주황 = 일부 실패(partial) / 빨강 = 실패 / 회색 = 키 없음(건너뜀) 또는 데모 모드
- **카드 목록** (연결 권장 순서):

| STEP | 채널 | 필요한 값 | 채우는 곳 |
|---|---|---|---|
| 1 | 카페24 Admin API | `CAFE24_MALL_ID`, `CAFE24_CLIENT_ID`, `CAFE24_CLIENT_SECRET` (+ 토큰은 DB 자동) | 카페24 어드민 |
| 1 | 카페24 통계 API | 위와 같음 (scope 에 `mall.read_analytics` 필요) | 접속통계 |
| 2 | GA4 | `GA4_PROPERTY_ID`, `GOOGLE_APPLICATION_CREDENTIALS_JSON` | GA4 탭, 방문자 |
| 3 | Meta 광고 + 소재 | `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` | 광고, 히스토리 |
| 4 | 네이버 검색광고 + 키워드 | `NAVER_SA_API_KEY`, `NAVER_SA_SECRET_KEY`, `NAVER_SA_CUSTOMER_ID` | 광고, 히스토리 |
| 5 | 네이버 데이터랩 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 경쟁사 |
| 6 | 카카오모먼트 + 소재 | `KAKAO_REST_API_KEY`, `KAKAO_AD_ACCOUNT_ID` (+ 토큰은 DB 자동) | 광고, 히스토리 |
| 6-b | 네이버 GFA | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `GFA_AD_ACCOUNT_NO` (또는 CSV) | 광고 |
| 7 | Google Ads + 소재 | `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET` | 광고, 히스토리 |
| 7 | 크리테오 | `CRITEO_CLIENT_ID`, `CRITEO_CLIENT_SECRET` | 광고 |
| 7 | 모비온 등 (CSV 업로드) | `data/manual/<채널>/` 에 CSV | 광고 |
| 8 | 텔레그램 / Slack 알림 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` / `SLACK_WEBHOOK_URL` | 브리핑 알림 |

채널별 발급 방법과 함정은 `channels.md`.

## 2. 최근 수집 로그

캡처: `screens/channels-02-collect-log.png`

- **보여주는 것**: `collect_log` 테이블 최신 50건 — 시각 · 날짜 · 소스 · 상태 · 메시지
- **상태 읽는 법**:
  - `ok` + "N건" — 정상
  - `skip` + "자격증명 없음" — 키가 없어서 건너뜀(오류 아님)
  - `partial` — 일부 채널만 실패. 메시지에 실패한 채널과 이유가 있다. 받은 데이터는 저장됐다.
  - `fail` — 그 소스 전체 실패. 메시지에 예외 내용. 기존 데이터는 지우지 않았다.
- **자주 보는 실패 메시지**:
  - `invalid_grant` (카페24) → 리프레시 토큰이 끊겼다. 재인증 필요(`channels.md` 카페24).
  - `401/403` + 권한 문구 → 키가 틀렸거나 광고 계정 권한이 없다.
  - `429` → 호출 제한. 다음 수집에서 자동 복구되는지 본다.
  - `insufficient_scope` → 카페24 앱 권한(scope)이 빠졌다.
