# 순차 셋업 가이드 — 틀 확인부터 채널 연결까지

이 문서 하나로 끝까지 간다. 각 단계는 **5~15분**, 끝날 때마다 "확인" 명령으로 검증한다.
상세 발급 화면은 `CONNECT-GUIDE.md` / `TOKEN-LOCATIONS.md`, 함정은 `NEW-CLIENT-CHECKLIST.md` §6.

```
0 틀 확인(데모) → 1 카페24 → 2 GA4 → 3 Meta → 4 네이버SA → 5 네이버 데이터랩
→ 6 카카오 → 7 Google Ads → 8 Slack → 9 무인 자동화(Neon + GitHub Actions + Render)
```

> 원칙: **쉬운 채널부터 하나씩.** 키가 없는 채널은 자동 스킵되고, 한 채널만 채워도 그 채널만 수집된다.
> 각 단계 끝에 `python scripts/smoke_live.py --check` 가 ✓ 이면 다음으로.

---

## STEP 0 — 틀 확인 (데모 데이터, 5분)

```bash
cd cafe24-ops-status
./scripts/dev.sh            # venv 자동 사용, secrets.env 없으면 예시 복사, 데모 30일 생성, 서버 기동
```
→ http://localhost:8000 — 상단 배지가 **데모 데이터** 로 뜨면 정상.
- **카페24 어드민** 탭: 브리핑·요약 카드·기간비교(전일/전주/전년)·매출/신규재구매/광고비/디바이스/방문자 상세/카테고리/베스트·접속통계 9블록·일별 상세
- **광고** 탭: 채널별 성과(+GA4 전환)·광고비/전환 추이·GA4 사이트 분석·경쟁사 트렌드
- **광고 히스토리** 탭: Meta 소재(피로도)·네이버 키워드·플레이스 / **주간 리포트** 탭: 주간|월간 토글, Word(.docx) 다운로드
- **채널 연결** 탭: 9개 채널 카드(회색=미설정) + 수집 로그 ← 앞으로 이 탭을 보며 하나씩 켠다

업체명·카테고리 그룹·경쟁사명을 먼저 바꿔 두자: `config/sources.yaml`(`brand`, `competitors`), `config/metrics.yaml`(`category_groups`).

---

## STEP 1 — 카페24 Admin API (매출·주문의 원천, 15분) ★ 가장 먼저

**담당자(쇼핑몰 어드민 권한자)가 할 일**
1. https://developers.cafe24.com 로그인 → **앱 만들기**(무료)
2. **권한(scope) 7개 전부 체크** — 하나라도 빠지면 그 지표가 오류 없이 `—` 로 비어 보인다:
   `mall.read_order` `mall.read_customer` `mall.read_community` `mall.read_product` `mall.read_category` `mall.read_application` `mall.read_analytics`
3. **Redirect URI** 에 `https://localhost` 등록 (로컬 발급용. 나중에 Render 주소도 추가)
4. 앱의 **Client ID / Client Secret** 복사

**내가 할 일**
```bash
cp config/secrets.env.example config/secrets.env    # (dev.sh 가 이미 복사했으면 생략)
```
`config/secrets.env` 수정:
```
CAFE24_OPS_MODE=live
CAFE24_MALL_ID=<몰아이디>          # https://<여기>.cafe24.com
CAFE24_CLIENT_ID=...
CAFE24_CLIENT_SECRET=...
CAFE24_REDIRECT_URI=https://localhost
```
토큰 발급 (⚠ 인가코드는 **1분 만료** — 1)→2) 를 연속으로):
```bash
.venv/bin/python scripts/cafe24_auth.py --authorize
# → 출력 URL 을 브라우저로 열고 '승인' → 주소창 https://localhost/?code=XXXX 의 XXXX 복사
.venv/bin/python scripts/cafe24_auth.py --code XXXX
# → "✓ 토큰 발급 + DB 저장", 부여 scope 7개 확인 (누락 경고가 뜨면 앱 권한 다시 체크 후 재인증)
```
**확인**
```bash
.venv/bin/python scripts/smoke_live.py --check              # 카페24 Admin ✓ / 통계 API ✓
.venv/bin/python scripts/run_all.py --reset --mode live --days 14   # 데모 비우고 실데이터 14일
```
→ 대시보드 새로고침: 배지 **LIVE**, 채널 연결 탭의 카페24 카드 2개가 녹색. 매출·주문·카테고리·담기 퍼널·검색어가 실데이터.
(방문자/전환율은 아직 `—` → STEP 2)

> 토큰은 DB(`app_kv`)에 저장되어 자동 갱신·회전된다. `secrets.env` 의 `CAFE24_ACCESS_TOKEN/REFRESH_TOKEN` 은 비워도 됨.
> 키를 재발급했다면 `scripts/cafe24_auth.py --reset` 으로 DB 옛 토큰을 비운 뒤 재인증.

---

## STEP 2 — GA4 (방문자·구매전환율, 10분)

카페24 Admin API 엔 방문자가 없어 **방문자수/전환율은 GA4 로만** 채워진다. (상세: `GA4-SETUP.md`)
1. Google Cloud Console → 프로젝트 → **API 라이브러리 → "Google Analytics Data API" 사용 설정**
2. **서비스 계정 만들기** → 키 → **JSON** 다운로드
3. GA4 → 관리 → **속성 액세스 관리** → 서비스계정 이메일 추가, 역할 **뷰어**
4. GA4 → 관리 → 속성 설정 → **속성 ID(숫자)**

`secrets.env`:
```
GA4_PROPERTY_ID=123456789                        # 숫자만 (복붙 히든문자 주의)
GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account",...}   # JSON 파일 내용 전체를 한 줄로
```
**확인**: `smoke_live.py --check` → GA4 ✓ → `run_all.py --mode live --days 14` → 요약 카드 방문자·전환율 채워짐, 방문자 추이에 GA4·카페24 두 선.

---

## STEP 3 — Meta 광고 (10분)

1. https://business.facebook.com/settings → 사용자 → **시스템 사용자** → 추가(관리자)
2. 시스템 사용자 → **자산 추가** → 광고 계정 → "성과 보기" 이상
3. **토큰 생성** → 앱 선택(없으면 developers.facebook.com 에서 앱 1개 생성 후 비즈니스 연결) → 만료 **"만료되지 않음"** → 권한 `ads_read` (+`read_insights`) → 생성·복사(1회만 노출)
4. 광고계정 ID: Ads Manager 좌상단 `act_` 뒤 숫자

```
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=1234567890
META_APP_ID= / META_APP_SECRET=     # (선택) 사용자 토큰일 때 60일 장기토큰 자동 교환
```
> ⚠ 그래프 API 탐색기 토큰은 **60일 만료** → 조용히 36일 결측 난 사례. 반드시 시스템 사용자 토큰.

**확인**: `smoke_live.py --check` → Meta ✓ → `run_all.py --mode live --days 14` → 광고 탭에 Meta 행.

---

## STEP 4 — 네이버 검색광고 SA (5분, 가장 쉬움 — 3개 값 모두 콘솔에서 복사)

1. https://searchad.naver.com → 도구 → **API 사용 관리** → 액세스 라이선스 발급
2. `액세스 라이선스` / `비밀키`(1회 노출, 저장) / 우상단 `CUSTOMER_ID`
```
NAVER_SA_API_KEY=...
NAVER_SA_SECRET_KEY=...
NAVER_SA_CUSTOMER_ID=...
```
**확인**: 광고 탭에 **네이버 파워링크 / 네이버 플레이스** 가 자동 분리되어 표시.

---

## STEP 5 — 네이버 데이터랩 (경쟁사 트렌드, 5분)

1. https://developers.naver.com → 애플리케이션 등록 → 사용 API 에 **"데이터랩(검색어트렌드)"** 추가
2. Client ID / Secret
```
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
```
`config/sources.yaml` 의 `competitors:` 에 브랜드명(최대 5개). **확인**: 광고 탭 경쟁사 검색 트렌드.

---

## STEP 6 — 카카오모먼트 (후순위)
developers.kakao.com 앱 + 모먼트 권한 → OAuth 액세스 토큰, moment.kakao.com 광고계정 ID.
```
KAKAO_ACCESS_TOKEN=... / KAKAO_AD_ACCOUNT_ID=...
```
⚠ 액세스 토큰 단기 만료(리프레시 자동화 미구현). 응답 필드는 실 키로 첫 1회 검증.

## STEP 7 — Google Ads (후순위, 개발자 토큰 승인 수일)
ads.google.com(MCC) → API 센터 개발자 토큰 → OAuth refresh/access 토큰 → Customer ID(대시 제거).
```
GOOGLE_ADS_DEVELOPER_TOKEN=... / GOOGLE_ADS_ACCESS_TOKEN=... / GOOGLE_ADS_CUSTOMER_ID=... / GOOGLE_ADS_LOGIN_CUSTOMER_ID=(MCC)
```

## STEP 8 — 알림: 텔레그램(권장) / Slack — PC·모바일에서 매일 브리핑 + 대시보드 링크 수신

**텔레그램 (5분)**
1. 텔레그램에서 **@BotFather** → `/newbot` → 이름·아이디 입력 → **봇 토큰** 복사
2. 만든 봇을 열어 아무 메시지나 1개 전송 (그룹에서 받으려면 봇을 그룹에 초대 후 메시지)
3. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates` → `"chat":{"id": 123456789}` 의 숫자가 **chat id** (그룹은 음수)
```
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
DASHBOARD_URL=https://<서비스명>.onrender.com     # 또는 아티팩트 링크 — 메시지의 '대시보드 열기' 버튼
```
**확인**: `python scripts/smoke_live.py --check` → 텔레그램 ✓ (테스트 메시지 도착) → `python scripts/notify.py` → 브리핑 + 버튼.
이후 매일 07:00 KST 수집 직후 브리핑이, 월요일 08:25 KST 에는 주간 리포트 .docx 가 텔레그램으로 온다. 수집 실패 채널도 같은 메시지에 🔴 로 표시.

**Slack (선택)**: api.slack.com/apps → Incoming Webhooks → `SLACK_WEBHOOK_URL=...`
(둘 다 없으면 토큰이 끊겨도 아무도 모른다 — keek 36일 결측 사례.)

---

## STEP 9 — 무인 자동화 (매일 07:00 KST 자동 수집 + 공개 URL)

로컬 SQLite 는 내 PC 에서만 보인다. 무료 스택으로 영속화·공개 (상세: `DEPLOY-FREE.md`, `GITHUB-ACTIONS.md`):

1. **GitHub**: 이 폴더를 저장소로 푸시(private 권장). `.github/workflows/` 가 main 에 있어야 schedule 동작.
2. **Neon**(neon.tech) → 프로젝트 → Connection string → GitHub **Secrets** `DATABASE_URL`
   (러너는 매번 초기화 → 외부 DB 없으면 카페24 회전 토큰이 유실돼 무인 수집이 깨진다)
3. Secrets 에 `secrets.env` 와 **같은 이름**으로 각 채널 값 등록 (있는 것만)
4. **카페24 토큰을 Neon 에 넣기** — 둘 중 하나:
   - 로컬: `DATABASE_URL="postgresql://..." .venv/bin/python scripts/cafe24_auth.py --authorize` → 승인 → `--code XXXX` (DB=Neon 에 저장)
   - Actions: `cafe24 authorize url` 실행 → 승인 → `cafe24 token fast` 에 code 입력 (사람이 1분 내 직접 클릭)
   - Redirect URI 는 개발자센터에 등록된 값과 **글자까지 동일**해야 한다
5. Actions → **ops daily collect** → Run workflow (`days: 30`, `reset: true` 최초 1회) → 백필
6. **Render**(render.com) → New → **Blueprint** → 저장소 선택 → `render.yaml` 인식 → 환경변수에 `DATABASE_URL` + 카페24/GA4 키 → Deploy
   → `https://<서비스명>.onrender.com` 에서 실데이터 대시보드. (무료는 15분 무접속 시 슬립 → `api smoke` 워크플로가 깨움)
7. 검증: Actions **api smoke** (`base_url` 입력) → 전 엔드포인트 200.

---

## 문제가 생기면

| 증상 | 원인/조치 |
|---|---|
| `invalid_grant` / 재인증 요구 | refresh 토큰 회전분 유실 → `cafe24_auth.py --reset` 후 `--authorize` 재발급. 코드에서 토큰은 항상 `Cafe24Client.from_store` 로만 |
| 후기·담기율·검색어가 빈 값 | scope 축소 재인증 → `cafe24_auth.py --status` 로 누락 scope 확인 → 7개 체크 후 재인증 |
| 통계 API 403 INVALID SCOPE | `mall.read_analytics` 누락 |
| 방문자/전환율 `—` | GA4 Data API 미사용설정 또는 서비스계정이 속성 뷰어가 아님 |
| Meta 401 code=190 | 토큰 만료 → 시스템 사용자 토큰으로 교체, DB 의 `meta_access_token` 비우기(`cafe24 token reset`) |
| 광고 탭 ROAS 가 너무 높음 | 크리테오·GFA·브랜드검색은 미연동(광고비 누락) — 업체에 고지 |
| 하루가 통째로 비었다 | 러너 UTC 날짜 문제 → `pipeline.yesterday()` 는 KST, 워크플로 `TZ: Asia/Seoul` 확인. `--days 3` 재수집으로 자가복구 |
| 신규가입수·회원가입율 | 카페24 API 로 조회 불가 — `—` 가 정상 |

로그: 채널 연결 탭 하단 **최근 수집 로그**, 또는 `GET /api/logs`.
