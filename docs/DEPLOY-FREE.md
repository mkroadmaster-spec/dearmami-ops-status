# 무료 스택 배포 체크리스트 (내일 그대로 따라하기)

모든 구성요소가 **무료 티어**입니다. 카드 등록 없이 가능한 것 위주.

| 역할 | 플랫폼 | 비용 | 비고 |
|---|---|---|---|
| 매일 수집 | GitHub Actions | 무료 | 이미 활성 (07:10 KST) |
| 데이터 영속 | Neon Postgres | 무료 | 카드 불필요 |
| 웹/API | Render Web Service | 무료 | 15분 무접속 시 슬립(콜드스타트 ~30초) |
| 알림(선택) | Slack Webhook | 무료 | — |

---

## 가치순 순서 (위→아래로 진행)

### 0. DATABASE_URL — 최우선 (5분) ⛳ 이게 없으면 데이터가 안 쌓임
1. https://neon.tech 가입(깃허브 로그인) → **Create project**
2. 대시보드의 **Connection string** 복사 (`postgresql://...?sslmode=require`)
3. GitHub 저장소 시크릿에 등록:
   https://github.com/leejiho-pslab/pslab/settings/secrets/actions/new
   - Name: `DATABASE_URL` / Value: 복사한 문자열
4. → 다음 수집부터 Neon 에 누적 시작. (수동 즉시 확인: Actions 탭에서 `ops daily collect` Run workflow)

### 1. 카페24 — 매출·전 KPI의 원천 (15분)
1. https://developers.cafe24.com → 앱 생성 → Client ID/Secret
2. Redirect URI `https://localhost`, scope `mall.read_order`,`mall.read_customer`
3. 토큰 발급: `python scripts/cafe24_auth.py --authorize` → 승인 → `--code <코드>`
4. 시크릿 등록: `CAFE24_MALL_ID`(=coversomeone1), `CAFE24_CLIENT_ID`, `CAFE24_CLIENT_SECRET`,
   `CAFE24_ACCESS_TOKEN`, `CAFE24_REFRESH_TOKEN`
   > 상세: CONNECT-GUIDE.md STEP1

### 2. Meta 광고 — 쉬움 (10분)
- https://developers.facebook.com → 액세스 토큰(`ads_read`) + 광고계정 ID
- 시크릿: `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`

### 3. 네이버 경쟁사 자동수집 — 산산기어/살로몬 (5분)
- https://developers.naver.com → 앱 등록(검색어트렌드+검색 API)
- 시크릿: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
- 경쟁사는 이미 `config/sources.yaml` 에 **산산기어 / 살로몬** 으로 설정됨.

### 4. 배포 (Render, 20분) — URL 로 접속 가능한 대시보드
1. https://render.com 가입(깃허브 로그인)
2. **New → Blueprint** → 이 저장소 연결 → 기본 브랜치 선택
3. `render.yaml` 자동 인식 → 시크릿 입력란에 **최소 `DATABASE_URL`** (+ 위에서 만든 키들) 붙여넣기
4. **Deploy** → `https://keek-ops-dashboard.onrender.com` 발급
   > GitHub Actions 와 같은 `DATABASE_URL` 을 쓰면, 수집한 실데이터가 그대로 화면에 뜬다.

### 5. (후순위) 카카오모먼트 / 구글애즈
토큰 승인이 까다로워 90% 이후로. 키만 채우면 커넥터는 이미 대기 중.

---

## ✅ "90% 완성" 정의
0(누적) + 1(매출) + 2(광고1채널) + 3(경쟁사) + 4(배포) 가 끝나면
**실데이터가 매일 자동 수집·누적되고, 공개 URL 로 보이는 대시보드** 완성.

## 막히면
각 단계의 에러 메시지 / Actions 로그 / `--check` 출력을 그대로 붙여주세요. 바로 잡아드립니다.
