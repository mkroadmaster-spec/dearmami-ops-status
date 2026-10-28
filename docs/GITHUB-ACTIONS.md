# GitHub Actions 무인 수집 가이드

이 웹 샌드박스는 외부 API egress 가 차단돼 라이브 수집이 안 됩니다. **GitHub Actions
러너는 외부 통신이 열려 있어** cafe24/Meta/Naver/Kakao 호출이 정상 동작합니다.
아래 순서로 설정하면 매일 자동으로 실데이터가 쌓입니다.

> **현재 활성화 대상: 카페24 · 네이버 검색광고(SA) · 메타** (카카오·구글은 추후)
> 이 3채널 커넥터는 스펙 검증·보강 완료(필드/엔드포인트/토큰회전). 발급 절차는 맨 아래 부록 참고.

```
[GitHub Actions(매일)] --실수집--> [무료 Postgres] <--읽기-- [대시보드/API]
```

---

## STEP 1 — 무료 Postgres 준비 (영속 저장소)
러너는 매번 초기화되므로 데이터는 외부 DB에 저장해야 합니다(특히 cafe24 회전 토큰).
무료 티어 아무거나:
- **Supabase**(supabase.com) → 프로젝트 → Settings → Database → Connection string(URI)
- **Neon**(neon.tech) → 프로젝트 → Connection string
- **Railway**(railway.app) → Postgres → Connect → Postgres Connection URL

받은 URL을 그대로 사용: `postgresql://user:pass@host:5432/dbname`
(코드는 `DATABASE_URL` 만 있으면 자동으로 Postgres 로 동작 — 별도 작업 없음)

---

## STEP 2 — GitHub Secrets 등록
**저장소 → Settings → Secrets and variables → Actions → New repository secret**

| Secret | 값 | 채널 |
|---|---|---|
| `DATABASE_URL` | STEP1 의 Postgres URL | **공통(필수)** |
| `CAFE24_MALL_ID` | `coversomeone1` | cafe24 |
| `CAFE24_CLIENT_ID` | `SFifOfmzX0Nh635bOfavxH` | cafe24 |
| `CAFE24_CLIENT_SECRET` | (앱의 Client Secret) | cafe24 |
| `CAFE24_ACCESS_TOKEN` / `CAFE24_REFRESH_TOKEN` | STEP3 에서 발급 | cafe24(최초 1회) |
| `META_ACCESS_TOKEN` | 시스템 사용자 토큰(ads_read) | Meta |
| `META_AD_ACCOUNT_ID` | `1513093573064263` | Meta |
| `NAVER_SA_API_KEY` / `NAVER_SA_SECRET_KEY` / `NAVER_SA_CUSTOMER_ID` | 검색광고 API | Naver SA |
| `KAKAO_ACCESS_TOKEN` / `KAKAO_AD_ACCOUNT_ID` | 카카오모먼트 | Kakao |
| `GOOGLE_ADS_*` | 개발자토큰/액세스토큰/Customer ID | Google |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 데이터랩/검색 | 경쟁사 |
| `SLACK_WEBHOOK_URL` | 인커밍 웹훅 | 알림(선택) |

> 채널은 **있는 것만** 채우면 됩니다. 빠진 채널은 자동 스킵.

---

## STEP 3 — cafe24 토큰 최초 발급 (회전은 이후 자동)
cafe24 access 토큰은 2시간, refresh 토큰은 2주 만료되며 갱신 시 회전됩니다.
**최초 토큰만 한 번** 발급해 두면, 이후 일일 잡이 자동 갱신해 Postgres(app_kv)에 보존합니다.

**방법 A — 로컬에서 (가장 안정적, 권장)**
인가코드는 발급 후 ~1분 만료라 로컬이 안전합니다.
```bash
# 1) 인가 URL 생성 → 브라우저 승인 → 주소창 code= 복사
python scripts/cafe24_auth.py --authorize --redirect-uri "https://keek-ops-dashboard.onrender.com"
# 2) 코드 교환 + Postgres 에 저장 (DATABASE_URL 은 STEP1 값)
DATABASE_URL="postgresql://..." \
CAFE24_MALL_ID=coversomeone1 CAFE24_CLIENT_ID=... CAFE24_CLIENT_SECRET=... \
python scripts/cafe24_auth.py --code <코드> --redirect-uri "https://keek-ops-dashboard.onrender.com" --to-db
```
→ 이러면 `CAFE24_ACCESS_TOKEN/REFRESH_TOKEN` Secret 없이도 DB에서 바로 동작.

**방법 B — Actions 워크플로**
저장소 → Actions → **cafe24 token bootstrap** → Run workflow → `code` 입력.
(단, CI 콜드스타트가 1분 넘으면 코드 만료로 실패 가능 → 그땐 방법 A)

---

## STEP 4 — 워크플로 활성화 & 실행
- 워크플로 파일(`.github/workflows/`)이 **기본 브랜치(main)** 에 있어야 schedule 이 동작합니다.
  → 이 브랜치를 main 에 머지하세요.
- 즉시 테스트: 저장소 → Actions → **ops daily collect (all channels)** → Run workflow
  (`days`에 14 입력 시 최근 14일 백필)
- 매일 07:10 KST 자동 실행.

---

## STEP 5 — 대시보드에서 보기
대시보드/API를 **같은 `DATABASE_URL`** 로 띄우면 수집된 실데이터를 그대로 읽습니다.
```bash
DATABASE_URL="postgresql://..." uvicorn api.main:app
# 또는 같은 환경변수로 ./scripts/dev.sh / docker compose
```

---

## 채널별 토큰 만료 주의
| 채널 | 만료/회전 | 무인 동작 |
|---|---|---|
| cafe24 | access 2h / refresh 2주(회전) | ✅ DB로 자동 갱신·보존 |
| Meta | 시스템 사용자 토큰 = 장수명 | ✅ 사실상 무기한 |
| Naver SA / DataLab | 키 고정 | ✅ |
| Kakao / Google | access 토큰 단기 만료 | ⚠ 만료 시 토큰 재발급 필요(리프레시 자동화는 추후) |

> Kakao/Google 은 액세스 토큰이 짧게 만료됩니다. 우선 cafe24·Meta·Naver 로 안정 운영하고,
> Kakao/Google 리프레시 자동화가 필요하면 알려주세요(커넥터에 추가 가능).

---

# 부록 — 활성 3채널 정확한 발급 절차

## A. 카페24 (✓ 정보 확보됨)
- `CAFE24_MALL_ID=coversomeone1`, `CAFE24_CLIENT_ID`, `CAFE24_CLIENT_SECRET` 확보.
- 남은 건 **최초 토큰 발급**(STEP 3) 한 번. 이후 access(2h)/refresh(2주) 회전은 DB가 자동 보존.
- 수집 지표: 매출(gross_sales)·주문수·객단가·신규가입. (방문자/전환율은 `CAFE24_VISITORS_PATH` 지정 시)

## B. 네이버 검색광고(SA)
검색광고는 **3개 값 모두 콘솔에서 바로 복사**(발급형 토큰 없음 → 가장 쉬움):
1. **searchad.naver.com** 로그인 → 우상단 **도구 → API 사용 관리**
2. `네이버 검색광고 API` → **액세스 라이선스 발급** → 아래 3개 복사:
   - `NAVER_SA_API_KEY` (액세스 라이선스)
   - `NAVER_SA_SECRET_KEY` (비밀키 — 발급 시 1회 노출, 꼭 저장)
   - `NAVER_SA_CUSTOMER_ID` (계정 우상단의 CUSTOMER_ID 숫자)
- 커넥터: 캠페인 목록 → /stats 로 노출·클릭·광고비·전환·전환매출 집계(100개 단위 청크).

## C. 메타 (광고계정 ID = 1513093573064263 확보, 토큰만 남음)
**시스템 사용자 토큰(장수명)** 발급 — 무인 운영에 최적:
1. **business.facebook.com/settings** (Coversomeone Corporation 비즈니스)
2. 좌측 **사용자 → 시스템 사용자** → 없으면 **추가**(이름 아무거나, 역할 관리자/직원)
3. 만든 시스템 사용자 선택 → **자산 할당** → 광고계정 **keek2** 에 권한 부여(관리/보기)
4. **앱 할당**: 앱이 없으면 developers.facebook.com 에서 앱 1개 생성 후 이 비즈니스에 연결
5. **토큰 생성(Generate token)** → 앱 선택 → 권한 **`ads_read`** 체크 → 생성
6. 나온 토큰을 `META_ACCESS_TOKEN` Secret 에, `META_AD_ACCOUNT_ID=1513093573064263`
- 커넥터: act_계정/insights(level=account)로 spend·impressions·clicks·구매전환·전환매출.
  (구매 전환은 omni_purchase→pixel 순으로 인식)

---

## 이 3채널만 켜고 시작하기 (체크리스트)
- [ ] 무료 Postgres → `DATABASE_URL`
- [ ] GitHub Secrets: `DATABASE_URL`, `CAFE24_MALL_ID/CLIENT_ID/CLIENT_SECRET`,
      `NAVER_SA_API_KEY/SECRET_KEY/CUSTOMER_ID`, `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`
- [ ] 카페24 최초 토큰 발급(로컬 `cafe24_auth.py --to-db` 또는 부트스트랩 워크플로)
- [ ] 워크플로를 main 에 머지 → Actions → Run workflow(`days: 14` 백필)
- [ ] 대시보드를 같은 `DATABASE_URL` 로 띄워 확인
