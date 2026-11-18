# 채널 연결 — 순서, 사용자에게 안내하는 법, 실제로 겪은 함정

**사용자에게 줄 안내문은 `easy-channel-guide.md`** 다(복사·붙여넣기 수준, 채널마다 같은 형식). 파일로 달라고 하면 `assets/guide/` 의 HTML(복사 버튼)·Word 를 준다. 내용을 고칠 때는 소스의 `scripts/guide_content.py` 한 곳만 고치고 `python scripts/build_guide.py` 로 세 형식을 다시 만든다.
이 문서는 **안내할 때 알아야 하는 것과 가이드에 없는 함정**을 모았다. 개발자용 상세는 소스의 `docs/SETUP-GUIDE.md`.

- 토큰 발급 워크플로의 `redirect_uri` 는 비워 두면 그 저장소의 대시보드 주소(`https://<owner>.github.io/<repo>/`)가 자동으로 들어간다. 매체에 등록한 리다이렉트 주소와 글자까지 같아야 한다.
- 승인 뒤 대시보드로 돌아오면 화면 아래에 "○○ 인증코드가 도착했습니다" 띠가 뜨고, 코드 복사 버튼과 토큰 워크플로 바로가기가 있다(카페24 1분, 카카오·구글·GFA 10분 안에 교환).

## 안내하는 방식

사용자는 개발자가 아니다. 지금까지 잘 통했던 방식:

1. **한 번에 한 채널만.** 쉬운 것부터: 카페24 → 네이버 검색광고 → 카카오 → 구글 → 크리테오 → GFA/모비온(CSV).
2. **매번 같은 형식**: `1단계 … 5단계`, 각 단계에 **열 링크**, **누를 버튼 이름**, **복사해 붙일 값**(코드 서식), GitHub Secrets 에 넣을 `Name | 값` 표, 마지막에 "○○ 됐어 라고 보내 주세요".
3. 사용자가 **화면 캡처를 보내면** 그 화면에서 무엇을 고르고 누를지만 답한다. 외부 서비스 화면은 직접 볼 수 없으므로 "버튼 이름이 다르면 캡처해 주세요"를 덧붙인다.
4. 사용자가 "됐어"라고 하면 직접 확인한다: `channel-check.yml` 실행 → 성공하면 그 채널만 2025-01-01부터 백필(`ads_only`) → 배포 → 결과 보고.
5. GitHub Secrets 는 사용자가 직접 넣어야 한다. 주소: `https://github.com/<owner>/<repo>/settings/secrets/actions` → **New repository secret**. 값 앞뒤 공백·줄바꿈이 흔한 실패 원인이다.

## 채널별

### 카페24 (STEP 1) — 모든 것의 시작

- 카페24 개발자센터에서 앱을 만들고 **scope 7개를 전부** 체크: `mall.read_order`, `mall.read_customer`, `mall.read_community`, `mall.read_product`, `mall.read_category`, `mall.read_application`, `mall.read_analytics`. 하나라도 빠지면 오류 없이 해당 지표만 `—` 가 된다.
- 인증 코드는 **1분 안에** 토큰으로 바꿔야 한다. 그래서 워크플로를 둘로 나눴다: `cafe24-authorize-url.yml`(승인 주소 출력) → 사용자가 승인 → `cafe24-token-fast.yml`(코드 입력, 주소 전체를 붙여도 된다).
- 리프레시 토큰은 **쓸 때마다 새것으로 바뀐다**(회전). 새 토큰을 저장하지 않으면 다음 실행에서 `invalid_grant`. 그래서 `Cafe24Client.from_store(store)` 로만 만들고 갱신 즉시 DB 에 쓴다. 회귀 테스트: `tests/test_cafe24_token_rotation.py`.
- DB 의 토큰이 Secret 보다 우선한다. 키를 재발급했으면 `cafe24-token-reset.yml` 로 DB 토큰을 지운 뒤 다시 인증한다.
- **가입자 수**는 개인정보 권한(`mall.read_privacy`)이 있어야 한다. 기본 구성에는 없다.
- **카테고리**는 주문에 없다 → `tab-ops.md` 7번.

### 네이버 검색광고 (STEP 4) — 가장 쉽다

- 광고 시스템 → 도구 → API 사용 관리에서 3개 값을 복사: 액세스라이선스(`NAVER_SA_API_KEY`), 비밀키(`NAVER_SA_SECRET_KEY`), 고객 ID(`NAVER_SA_CUSTOMER_ID`).
- **API 키는 그 키를 만든 계정의 것이다.** 대행사 계정으로 만든 키로는 광고주 계정 데이터를 못 본다. 광고주 계정에서 직접 발급하거나 권한을 받아야 한다. `naver-check.yml` 로 고객 ID 가 맞는지 확인할 수 있다.
- 파워링크/플레이스는 자동 분리된다.

### 카카오모먼트 (STEP 6)

- 카카오 디벨로퍼스 비즈 앱 + 카카오모먼트 API 권한 → 비즈니스 인증 OAuth: `kakao-authorize-url.yml` → 승인 → `kakao-token.yml`. 토큰은 DB 에 저장되고 자동 갱신된다.
- 광고계정 번호 `KAKAO_AD_ACCOUNT_ID` 는 모먼트 주소창의 숫자다.
- 리포트 API 제한이 매우 엄격하다 → `tab-history.md` 카카오 항목.

### Google Ads (STEP 7)

- 개발자 토큰(관리자 계정 MCC 의 API 센터) + OAuth 클라이언트 → `google-authorize-url.yml` → `google-token.yml`.
- 개발자 토큰이 **Explorer 등급**이어도 자기 계정 조회는 된다. 다만 하루 약 2,880회 제한 → 30일 묶음 조회.
- `GOOGLE_ADS_CUSTOMER_ID` 는 하이픈 없는 10자리. 관리자 계정 아래 계정이면 `GOOGLE_ADS_LOGIN_CUSTOMER_ID` 에 관리자 계정 번호.
- API 버전은 자주 종료된다. `ads_google.search()` 가 버전을 차례로 시도한다.

### Meta (STEP 3)

- 비즈니스 설정에서 **시스템 사용자**를 만들고 `ads_read` 권한 토큰을 발급한다(만료 없음). 일반 사용자 토큰은 60일 뒤 조용히 끊긴다.
- `META_AD_ACCOUNT_ID` 는 `act_` 뒤 숫자.

### 크리테오 (STEP 7)

실제로 진행한 순서와 막힌 곳:

1. `https://partners.criteo.com` 로그인 → 조직(Organization) 만들기: Company name, **Type of company = Advertiser**, 이메일, Country = Korea, Website.
2. **Start building** → 앱 이름 → 서비스 **Marketing Solutions** → 인증 **Client Credentials**.
3. Authorizations 화면: **Analytics = Read** 는 필수, Campaigns·Creatives 도 Read 권장(전부 Read 로 해도 읽기 전용이라 안전) → **Activate app**.
4. **Create new key** → 텍스트 파일이 내려받아진다. 안에 `client_id`, `client_secret`. 화면의 'API key' 열이 client_id 다. secret 은 이때만 보인다.
5. **Create new consent URL** → 그 링크를 열어 **Portfolio access** 에서 광고주를 체크 → 승인.
   - 여기서 광고주가 **`(Not Authorized)` 회색**으로 나오면 로그인한 계정에 그 광고 계정의 관리자 권한이 없는 것이다. 이대로 Ok 를 누르면 광고주 없이 승인돼 데이터를 못 받는다. → 계정 권한을 Admin 으로 올려 달라고 하거나, 동의 링크를 관리자(대행사·크리테오 담당자)에게 보내 대신 승인받는다.
6. Secrets: `CRITEO_CLIENT_ID`, `CRITEO_CLIENT_SECRET` (광고주 ID 는 선택 — 비우면 접근 가능한 광고주 전체 합산).
7. 확인: `probe.yml` 에 `script=criteo_probe` — DB 없이 토큰 발급 · 승인된 광고주 · 리포트 응답 모양을 본다. (`channel-check.yml` 은 DB 접속이 필요하다.)
- **리포트 응답은 BOM 이 붙은 세미콜론(;) 구분 CSV 다.** 문서 예시처럼 쉼표로 읽으면 오류 없이 전부 0 이 된다(실제로 겪음). `parse_report()` 가 BOM 을 떼고 구분자를 판별한다. 날짜는 `YYYY-MM-DD`, 금액은 소수점 표기.
- 하루씩 부르지 않고 60일 구간을 한 번에 받아 실행 중 기억한다(`daily()` → `range_by_day()`).
- 권한을 새로 받은 뒤에는 **동의 링크를 새로 만들어** 다시 승인한다. 승인 여부는 동의 화면(consent.criteo.com)의 앱 칸에 광고주가 `Authorized` 로 나오는지, 또는 `criteo_probe` 의 "승인된 광고주 수"로 확인한다.
- 관리자 승인을 못 받으면 CSV 업로드로 대체한다.

### 네이버 GFA · 모비온 (CSV)

- GFA 는 API 사용 신청에 네이버 승인이 필요하다. 그 전에는 관리 화면에서 일별 리포트 CSV 를 내려받아 `data/manual/gfa/` 에 올린다. 모비온은 `data/manual/mobon/`.
- 형식은 `docs/CSV-CHANNELS.md`. 파일을 커밋하면 다음 수집 때 반영된다. API 가 연결되면 API 가 우선한다.

### 알림 (STEP 8)

- 텔레그램: BotFather 로 봇 생성 → `TELEGRAM_BOT_TOKEN`, 채팅 ID → `TELEGRAM_CHAT_ID`. 매일 수집 뒤 브리핑과 대시보드 링크가 온다.
- Slack: `SLACK_WEBHOOK_URL`.

## 연결 확인 방법

| 방법 | 언제 |
|---|---|
| `python scripts/smoke_live.py --check` | 로컬에 키가 있을 때 — 설정된 채널만 1회 호출 |
| Actions `channel-check.yml` (`channels=kakao,google,gfa,criteo`) | 운영 Secrets 로 확인 |
| Actions `naver-check.yml` | 네이버 고객 ID 확인 |
| 채널 연결 탭 카드 색 + 수집 로그 | 수집 뒤 |
