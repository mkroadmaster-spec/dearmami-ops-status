# GA4 연동 (방문자수 · 구매전환율)

카페24 Admin API에는 방문자 엔드포인트가 없어 **방문자수/구매전환율**은 GA4로만 채울 수 있습니다.
코드는 이미 준비되어 있고(게이트형), 아래 **시크릿 2개만** 넣으면 다음 수집부터 자동으로 채워집니다.
설정 전에는 비활성이라 기존 동작에 영향이 없습니다.

## 0. 사전 조건
- keek 자사몰(coversomeone1)에 **GA4 속성**이 설치되어 데이터가 쌓이고 있어야 합니다.
  (미설치 시 먼저 GA4 설치 → cafe24 ‘마케팅 → Google Analytics(GA4)’ 또는 헤더 스크립트)

## 1. 서비스 계정 + 키 만들기 (무료)
1. Google Cloud Console → 프로젝트 생성(또는 기존)
2. **API 및 서비스 → 라이브러리 → “Google Analytics Data API” 사용 설정**
3. **사용자 인증 정보 → 서비스 계정 만들기** → 이름 아무거나 → 완료
4. 만든 서비스 계정 → **키 → 키 추가 → JSON** → 키 파일(.json) 다운로드

## 2. GA4에 읽기 권한 부여
1. GA4 → **관리(⚙️) → 속성 액세스 관리 → +추가**
2. 위 서비스 계정 이메일(`...@....iam.gserviceaccount.com`) 추가, 역할 **뷰어**
3. **관리 → 속성 설정**에서 **속성 ID(숫자, 예: 123456789)** 확인

## 3. GitHub 시크릿 2개 등록
저장소 → Settings → Secrets and variables → Actions → **New repository secret**

| 시크릿 이름 | 값 |
|---|---|
| `GA4_PROPERTY_ID` | 속성 ID 숫자 (예: `123456789`) |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | 다운로드한 **JSON 파일 내용 전체**를 그대로 붙여넣기 |

## 4. 끝 — 자동 반영
- 다음 일일 수집(07:00 KST)부터 `visitors`(방문자수)와 `conversion_rate`(=구매건수/방문자수)가 자동 저장됩니다.
- 일일 브리핑/대시보드/검수에 방문자·전환율이 나타납니다.
- 과거 방문자도 채우려면(선택): Actions → **ops backfill** 수동 실행 시 `reset=true`, `skip=competitor,creative,ads`
  (cafe24 재수집 시 GA4 방문자도 일자별로 함께 기록됨).

## 확인
- Actions → **ops verify (data accuracy)** 로그의 `방문자수 N/일` 가 0에서 증가하면 정상.
- 동작 원리: `cafe24_ops/clients/ga4.py`(GA4 Data API runReport → totalUsers),
  `collectors/cafe24.py`(방문자 GA4 우선), 전환율은 `collectors/cafe24.py:visitor_metrics`.
