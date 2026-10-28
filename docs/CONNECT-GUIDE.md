# 실데이터 연결 가이드 (무료 솔루션 · 순차 진행)

채널별 **무료 API**로 자격증명을 발급받아 `config/secrets.env` 에 채우고, 실데이터를
수집해 대시보드에서 확인하는 순서다. **쉬운 채널부터** 하나씩 켜면 된다(키 없는 채널은 자동 스킵).

> 핵심 흐름: `secrets.env 채움` → `python scripts/run_all.py --mode live --date <어제>` → `대시보드 확인`
> 채널 하나만 채워도 그 채널만 수집된다. 점진적으로 늘려가면 됨.

## STEP 0 — 준비

```bash
cd cafe24-ops-status
pip install -r requirements.txt
cp config/secrets.env.example config/secrets.env   # 여기에 값 채움
# sources.yaml 의 mall_id / 각 광고계정 account_id 도 실제 값으로
```

`CAFE24_OPS_MODE=live` 로 둔다. 채울 때마다 아래 "확인" 명령으로 검증.

---

## STEP 1 — 카페24 Admin API  *(무료, 가장 먼저)*

자사몰 매출/주문/방문/회원의 원천. 쇼핑몰에 기본 포함(무료).

1. **카페24 개발자센터**(developers.cafe24.com) 로그인 → 앱 만들기(무료)
2. 권한(scope): `mall.read_order`, `mall.read_customer` / Redirect URI 에 `https://localhost` 등록
3. 앱의 **Client ID / Secret** 를 `secrets.env` 에 먼저 입력:
   ```
   CAFE24_MALL_ID=keek
   CAFE24_CLIENT_ID=...
   CAFE24_CLIENT_SECRET=...
   ```
4. **OAuth 토큰 발급**(헬퍼 사용):
   ```bash
   python scripts/cafe24_auth.py --authorize --redirect-uri https://localhost
   # → 출력된 URL 을 브라우저로 열고 '승인' → 주소창의 code= 값 복사
   python scripts/cafe24_auth.py --code <복사한코드> --redirect-uri https://localhost
   # → access/refresh 토큰 자동 저장 + secrets.env 에 넣을 줄 출력
   ```
5. **확인**: `python scripts/smoke_live.py --check` → orders/count 가 뜨면 OK

> 토큰 만료(2시간)는 client_id/secret 있으면 자동 갱신.

---

## STEP 2 — Meta(페이스북/인스타) 광고  *(무료 API)*

1. **developers.facebook.com** → 앱 생성(무료) → Marketing API 추가
2. 권한 `ads_read` 로 액세스 토큰 발급(시스템 사용자 토큰 권장 — 장수명)
3. 광고계정 ID 확인 (`act_` 뒤 숫자)
4. `secrets.env`:
   ```
   META_ACCESS_TOKEN=...
   META_AD_ACCOUNT_ID=1234567890        # 또는 sources.yaml meta account_id
   ```
5. **확인**: `python scripts/run_all.py --mode live --date <어제>` → 로그에 `meta N건`

---

## STEP 3 — 네이버 데이터랩(경쟁사 검색 트렌드)  *(무료 API)*

1. **developers.naver.com** → 애플리케이션 등록(무료) → "데이터랩(검색어트렌드)" API 사용
2. `client_id` / `client_secret` 발급
3. `secrets.env`:
   ```
   NAVER_CLIENT_ID=...
   NAVER_CLIENT_SECRET=...
   ```
4. `config/sources.yaml` 의 `competitors:` 에 추적할 브랜드명 입력
5. **확인**: live 실행 후 경쟁사 탭의 "네이버 트렌드 흐름"에 실데이터

> ratio 는 상대 트렌드 지수(0~100). 절대 검색량 아님.

---

## STEP 4 — 네이버 검색광고(SA)  *(무료 API)*

1. **searchad.naver.com** → 도구 → "API 사용 관리"에서 라이선스 발급(무료)
2. `액세스 라이선스(API_KEY)`, `비밀키(SECRET_KEY)`, `CUSTOMER_ID(광고주 ID)` 확인
3. `secrets.env`:
   ```
   NAVER_SA_API_KEY=...
   NAVER_SA_SECRET_KEY=...
   NAVER_SA_CUSTOMER_ID=...
   ```
4. **확인**: live 실행 → 로그에 `ads ...`(naver 채널 포함), 광고 탭 Naver 카드

---

## STEP 5 — 카카오모먼트 광고  *(무료 API)*

1. **kakao developers / business** 에서 앱 + 카카오모먼트 권한
2. OAuth 액세스 토큰(모먼트 scope), 광고계정 ID 확인
3. `secrets.env`:
   ```
   KAKAO_ACCESS_TOKEN=...
   KAKAO_AD_ACCOUNT_ID=...
   ```
4. **확인**: live 실행 → 광고 탭 Kakao 카드

---

## STEP 6 — Google Ads  *(무료 API · 개발자 토큰 승인 필요)*

가장 절차가 김(개발자 토큰 승인). 다른 채널 먼저 돌려보고 나중에 붙여도 됨.

1. **Google Ads API Center** → 개발자 토큰 신청(무료, 테스트 액세스는 즉시)
2. OAuth2 동의 → refresh token → access token 발급
3. `customer_id`(대시 없는 10자리), MCC면 `login_customer_id`
4. `secrets.env`:
   ```
   GOOGLE_ADS_DEVELOPER_TOKEN=...
   GOOGLE_ADS_ACCESS_TOKEN=...
   GOOGLE_ADS_CUSTOMER_ID=...
   GOOGLE_ADS_LOGIN_CUSTOMER_ID=...   # MCC 사용 시
   ```
5. **확인**: live 실행 → 광고 탭 Google 카드

---

## STEP 7 — 알림(선택)  *(Slack 무료)*

1. **api.slack.com** → Incoming Webhook 생성(무료) → URL 복사
2. `SLACK_WEBHOOK_URL=...`
3. **확인**: `python scripts/notify.py` → Slack 전송

---

## STEP 8 — 저장소/실행

- **DB(무료)**: 기본 SQLite(로컬, 무료). 운영 영속화는 무료 Postgres 티어(Supabase/Neon/Railway):
  ```
  DATABASE_URL=postgresql://user:pass@host:5432/db
  ```
- **수집 실행**:
  ```bash
  python scripts/run_all.py --mode live --date 2026-06-17     # 1일
  python scripts/run_all.py --mode live --days 14             # 최근 14일 백필
  ```
- **대시보드**:
  ```bash
  ./scripts/dev.sh                 # API + 대시보드
  # 또는 docker compose up --build
  ```
- **무인 자동화(무료)**: `.github/workflows/cafe24-daily-collect.yml` 에 GitHub Secrets 로
  같은 키들을 넣으면 매일 자동 수집(GitHub Actions 무료 한도).

---

## 채널별 상태 요약

| 채널 | 무료 | 커넥터 | 확인 위치 |
|------|------|--------|-----------|
| 카페24 Admin API | ✅ | ✅ (주문·방문·가입) | 카페24 탭 |
| Meta 광고 | ✅ | ✅ | 광고 탭 Meta |
| 네이버 데이터랩 | ✅ | ✅ | 경쟁사 탭 트렌드 |
| 네이버 검색광고(SA) | ✅ | ✅ | 광고 탭 Naver |
| 카카오모먼트 | ✅ | ✅ | 광고 탭 Kakao |
| Google Ads | ✅(승인) | ✅ | 광고 탭 Google |
| Slack 알림 | ✅ | ✅ | notify.py |

> 광고 소재 이미지/경쟁사 광고·후기 크롤링은 다음 단계(소재 리포트 권한 / 크롤링 정책 확정 후).
> 각 커넥터의 HTTP 엔드포인트·버전은 **실 키로 첫 1회 검증** 권장(응답 매핑 로직은 단위 테스트 완료).
