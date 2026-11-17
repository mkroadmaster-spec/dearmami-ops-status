# 운영 — 수집·백필·배포·문제 해결

운영 환경: **GitHub Actions**(수집·배포) + **Neon Postgres 무료**(저장) + **GitHub Pages**(화면). 전부 무료다.
`<R>` = `<owner>/<repo>` (디어마미: `mkroadmaster-spec/dearmami-ops-status`).

## 워크플로 목록

| 파일 | 하는 일 | 실행 |
|---|---|---|
| `daily-collect.yml` | 전 채널 수집 | 매일 07:00 KST(최근 3일) + 수동 |
| `pages-deploy.yml` | 정적 대시보드 생성·배포 | 매일 07:40 KST + `dashboard/**` 푸시 + 수동 |
| `cafe24-weekly-report.yml` | 지난주 재수집 + Word 리포트 | 매주 월 08:25 KST |
| `cafe24-authorize-url.yml` / `cafe24-token-fast.yml` / `cafe24-token-reset.yml` | 카페24 토큰 발급·초기화 | 수동 |
| `kakao-authorize-url.yml` / `kakao-token.yml` | 카카오 토큰 | 수동 |
| `google-authorize-url.yml` / `google-token.yml` | 구글 토큰 | 수동 |
| `gfa-authorize-url.yml` / `gfa-token.yml` | GFA 토큰 | 수동 |
| `channel-check.yml` | 채널 인증 확인 (`channels=kakao,google,gfa,criteo`) | 수동 |
| `naver-check.yml` | 네이버 고객 ID 확인 | 수동 |
| `data-coverage.yml` | 소스·채널별 쌓인 날짜 범위와 빈 날짜 수 (읽기 전용) | 수동 |
| `probe.yml` | 진단 스크립트 실행 (`script=`, `args=`) | 수동 |
| `api-smoke.yml` | 배포 주소 응답 확인 | 주기 |

## 직접 실행하는 법 (`gh` CLI)

```bash
# 수집: 최근 3일 (기본)
gh api -X POST repos/<R>/actions/workflows/daily-collect.yml/dispatches -f ref=main

# 백필: 특정 날짜부터 어제까지 전부
gh api -X POST repos/<R>/actions/workflows/daily-collect.yml/dispatches -f ref=main \
  -f 'inputs[from_date]=2025-01-01'

# 일부 소스만: skip 에 건너뛸 수집기 이름을 콤마로
#   수집기 이름: cafe24, cafe24_analytics, ga4, ads, creative, google_creative, kakao_creative, naver_keyword, competitor
gh api -X POST repos/<R>/actions/workflows/daily-collect.yml/dispatches -f ref=main \
  -f 'inputs[from_date]=2025-01-01' \
  -f 'inputs[skip]=cafe24,cafe24_analytics,ga4,creative,google_creative,kakao_creative,naver_keyword,competitor' \
  -f 'inputs[ads_only]=criteo'      # 광고 중 이 채널만. 다른 채널 데이터는 보존된다

# 배포
gh api -X POST repos/<R>/actions/workflows/pages-deploy.yml/dispatches -f ref=main

# 상태 · 로그
gh run list -R <R> --limit 5
gh run view <run_id> -R <R> --log | grep -E "run_all\]|\[progress\]"
```

수동 화면: 저장소 → **Actions** → 워크플로 선택 → **Run workflow**.

### 꼭 알아야 하는 동작

- **수집은 한 번에 하나만 돈다**(`concurrency: ops-collect`). 대기열에는 **하나만** 설 수 있어서, 대기 중인 실행이 있는데 또 실행하면 **먼저 대기하던 것이 취소된다.** 앞 실행이 `in_progress` 가 된 것을 확인한 뒤 다음 것을 건다.
- **푸시 직후 바로 실행하지 않는다.** 원격 `main` 이 방금 올린 커밋이 된 것을 확인하고(몇 초) 실행한다. 아니면 옛 코드로 돈다.
- **로그는 실행이 끝나야 보인다.** 긴 백필 중에는 진행률을 볼 수 없다. 백필은 30일마다 `[progress] n/N일 · 경과 · 예상 잔여` 를 찍으므로 끝난 뒤 확인하거나, DB 를 진단으로 직접 본다(아래).
- **한 작업은 최대 6시간.** 넘을 것 같으면 소스를 나눠 돌린다.
- `gh api … dispatches` 가 HTTP 500 을 주면 몇 초 뒤 다시 시도한다.
- 수집이 끝나도 화면은 그대로다. **배포를 해야 화면이 바뀐다.**

### 백필에 걸리는 시간 (680일 기준, 실제 측정)

| 소스 | 시간 | 비고 |
|---|---|---|
| 카페24 접속통계 + 구글 소재 | 약 1.5시간 | |
| 네이버 검색광고 + 키워드 | 약 3시간 | 달마다 노출 키워드 선별 후 하루 9초 |
| 카카오 소재 | 약 3.5시간 | 31일 구간당 수 분 (호출 제한) |
| 상품 카테고리 채우기 | 약 1시간 | 1만 상품, 1회만 |

## 진단 (`probe.yml`)

응답 모양을 모르거나 숫자가 이상할 때 추측하지 말고 진단부터 돌린다.

```bash
gh api -X POST repos/<R>/actions/workflows/probe.yml/dispatches -f ref=main \
  -f 'inputs[script]=analytics_probe' -f 'inputs[args]=size'
```

인자가 없는 진단은 `inputs[args]` 를 빼고, 있는 것은 그대로 넣는다. 예:

```bash
gh api -X POST repos/<R>/actions/workflows/probe.yml/dispatches -f ref=main -f 'inputs[script]=category_probe'
gh api -X POST repos/<R>/actions/workflows/probe.yml/dispatches -f ref=main \
  -f 'inputs[script]=category_fill' -f 'inputs[args]=--reclassify'
```

로컬에 키(`config/secrets.env`)와 `DATABASE_URL` 이 있으면 `python scripts/<script>.py <args>` 로 같은 것을 돌릴 수 있다.

| script | args | 알려주는 것 |
|---|---|---|
| `analytics_probe` | `size` | DB 크기, 소스별 행 수·날짜 범위, 테이블 크기 |
| `analytics_probe` | `YYYY-MM-DD` | 카페24 통계 API 경로별 응답 키·첫 행, DB 지표 합계 |
| `collect_probe` | `수집기,… 날짜 날짜…` | 수집기를 DB 저장 없이 돌려 소요 시간·건수·오류만 |
| `category_probe` | `[카테고리번호…]` | 카테고리 트리, 상품의 카테고리 소속 모양 |
| `category_fill` | (`--reclassify`) | 판매 상품의 카테고리 매핑 채우기. `--reclassify` = 그룹 정의를 고친 뒤 전체 재분류 |
| `google_probe` / `kakao_probe` | (`fields`) | 광고 API 구조 |

**저장소가 Public 이면 Actions 로그도 공개된다.** 진단 스크립트는 건수·키 이름·날짜만 찍고 매출·광고비 금액은 찍지 않는다. 새 진단을 만들 때도 이 규칙을 지킨다.

## DB 용량 (Neon 무료 0.5GB)

- 행 하나가 약 0.4KB. 디어마미는 2025-01-01부터 약 85만 행, 429MB 였다.
- 그래서 하루 저장 상한을 둔다: 접속통계(상품 100·판매 50·검색어 100·도메인 50·페이지 30), 네이버 키워드 60, 카카오 소재 40. 0 인 지표는 저장하지 않는다.
- 용량이 차면: ① 가장 큰 소스(`cafe24_analytics`)의 상한을 줄이고 재수집 ② 오래된 상세 행(상품·키워드 단위)을 지우고 `kpi_daily` 는 유지 ③ 유료 전환. 지우기 전에 반드시 사용자에게 확인받는다.
- 새 소스를 붙일 때는 **먼저 하루치 행 수를 재고**(`collect_probe`) 기간을 곱해 본다. 네이버 키워드는 상한 없이 하루 2,600행이라 한도를 넘길 뻔했다.

## 배포

- `pages-deploy.yml`: `DATABASE_URL` 이 있으면 실데이터, 없으면 데모 75일로 빌드. `DASHBOARD_PASSWORD` 가 있으면 암호화.
- 사전 설정: 저장소 Settings → Pages → Source = **GitHub Actions**. 무료 플랜은 Public 저장소만 가능하다(그래서 비밀번호 암호화가 필수다).
- 주소: `https://<owner>.github.io/<repo>/`
- 사용자에게는 배포 후 **Ctrl+F5(강력 새로고침)** 를 안내한다.

## 화면을 고친 뒤 확인하는 법

실제 데이터 페이지는 암호화돼 있고 세션에서 받을 수 없는 경우가 많다. 데모로 확인한다.

```bash
DB=sqlite:////tmp/demo.db
DATABASE_URL=$DB CAFE24_OPS_MODE=demo .venv/bin/python scripts/run_all.py --reset --mode demo --days 75
DATABASE_URL=$DB CAFE24_OPS_MODE=demo DASHBOARD_PASSWORD= .venv/bin/python scripts/export_static.py --out /tmp/site/index.html
```

그다음 Playwright 로 `file:///tmp/site/index.html` 을 열어 해당 탭을 캡처하고 확인한다: 콘솔 오류 0, 390px 폭에서 `document.documentElement.scrollWidth == 390`. 이 스킬의 캡처도 이 방법으로 만들었다(`scripts/capture_screens.js`).

데모로만 확인했으면 사용자에게 "데모 데이터로 확인했고 실제 화면은 직접 보지 못했다"고 말한다.

## 문제 해결

| 증상 | 먼저 볼 것 | 흔한 원인 |
|---|---|---|
| 화면이 예전 그대로 | 배포가 돌았나, 강력 새로고침 | 수집만 하고 배포 안 함 |
| 특정 채널만 비어 있음 | 채널 연결 탭 카드·로그 | 키 없음(skip), 권한, 토큰 만료 |
| 전부 0 또는 `—` | `analytics_probe` 로 응답 모양 | 필드 이름이 달라 0 으로 저장, scope 누락 |
| 카테고리가 전부 '기타' | `tab-ops.md` 7번의 순서 | 그룹 이름이 그 몰의 카테고리와 안 맞음 → `category_groups` 수정 후 `category_fill --reclassify` |
| 소재 피로도가 늘 '정상' | 선택 기간 | 7일 이하면 비교 구간이 같아 하락률 0 → 14일·30일로 |
| 버튼을 눌러도 정렬·필터가 안 바뀜 | 정적 페이지인가 | 스냅샷엔 한 벌뿐 → 화면에서 정렬하도록 |
| "snapshot 에 없는 경로" | `export_static.py`, `snapGet()` | 새 API 를 스냅샷에 안 넣음 |
| 백필이 몇 시간째 안 끝남 | `collect_probe` 로 하루치 시간 측정 | 날짜마다 목록 재조회, 호출 제한(429) |
| `connection is closed` | — | Neon 이 쉰 연결을 끊음. `store._cursor_do` 가 재연결한다(이미 반영) |
| 카페24 `invalid_grant` | 토큰 초기화 후 재인증 | 리프레시 토큰 회전분 유실 |
| 하루가 통째로 빠짐 | 날짜 계산 | UTC 로 계산함. `pipeline.yesterday()` 는 KST |
| 어제 숫자가 바뀜 | — | 정상. 플랫폼의 지연 확정. 최근 3일 재수집이 보정한다 |

## 비밀 값

- 저장소에 키를 커밋하지 않는다. `config/secrets.env` 는 gitignore.
- 운영 값은 GitHub Secrets(같은 이름). 자주 바뀌는 토큰은 DB `app_kv`.
- 키가 노출됐으면 `docs/SECURITY-ROTATION.md` 순서로 재발급한다.
- 세션 환경에 따라 `gh secret set` 이 막혀 있을 수 있다. 그때는 사용자가 Secrets 화면에서 직접 넣는다.
