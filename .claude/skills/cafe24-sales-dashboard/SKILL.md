---
name: cafe24-sales-dashboard
description: 카페24 자사몰 매출·방문·광고 운영 대시보드(cafe24-ops-status)를 그대로 설치·운영·수정·복제하는 스킬. 화면 8탭(카페24 어드민, 광고, 광고 히스토리, GA4, 경쟁사, 주간·월간 리포트, 채널 연결)의 영역별 캡처와 지표 정의·계산식·코드 위치, 전체 소스 코드, 채널 연결(카페24·네이버 검색광고·GFA·카카오모먼트·구글·Meta·크리테오·모비온) 가이드, GitHub Actions 수집·백필·배포 운영법을 담고 있다. "매출 대시보드", "운영 대시보드", "카페24 대시보드", "광고 대시보드", "ROAS·광고비·전환 숫자가 이상해", "데이터가 안 들어와", "채널 연결 가이드", "백필", "새 업체로 복제", "대시보드에 그래프·탭 추가", "주간 리포트" 같은 요청이면 대시보드라는 말이 없어도 이 스킬을 먼저 읽는다.
---

# 카페24 매출 대시보드 (cafe24-ops-status)

카페24 자사몰의 **매출·주문·방문·광고 성과를 매일 자동 수집해 한 화면에서 보는 대시보드**다.
디어마미(dearmami.co.kr)에 실제로 구축·운영한 것을 그대로 담았다. 무료 도구만 쓴다(GitHub Actions + Neon Postgres 무료 + GitHub Pages).

이 스킬에는 세 가지가 들어 있다.

1. **화면 학습 자료** — 탭·영역마다 캡처 1장 + 무엇을 보여주는지, 어디서 온 숫자인지, 어떻게 계산하는지, 코드가 어디 있는지 (`references/tab-*.md`, `references/screens/*.png`)
2. **전체 소스 코드** — `assets/cafe24-ops-status-src.zip` (Python/FastAPI + 단일 HTML 대시보드 + 워크플로)
3. **운영 지식** — 채널 연결 순서와 함정, 백필·배포 방법, 겪었던 장애와 해결책

캡처는 전부 **데모 데이터**(가짜 숫자)다. 화면 구성은 실제와 같다.

## 먼저 할 일: 코드가 어디 있는지 확인

사용자의 요청을 처리하기 전에 작업할 코드가 있는지 본다.

- **이미 저장소가 있는 경우** (작업 폴더에 `cafe24_ops/`, `dashboard/index.html` 이 보이거나, 사용자가 GitHub 저장소를 알려준 경우) → 그 저장소에서 작업한다. 동봉 소스보다 저장소가 최신이다.
- **코드가 없는 경우** → 동봉 소스를 푼다.

```bash
bash <이 스킬 폴더>/scripts/install_source.sh ~/cafe24-ops-status
```

이 스크립트는 소스를 풀고, 가상환경을 만들고, 데모 데이터 75일치를 생성하고, 테스트를 돌린 뒤 서버 없이 열리는 `dist/index.html` 을 만든다. 끝나면 그 파일을 브라우저로 열어 8탭이 캡처와 같은지 확인한다. 외부 키는 하나도 필요 없다.

원본 저장소: `https://github.com/mkroadmaster-spec/dearmami-ops-status` (공개). 접근할 수 있으면 `git clone` 이 더 낫다.

## 요청별로 읽을 파일

필요한 것만 읽는다. 전부 읽을 필요 없다.

| 사용자의 요청 | 읽을 파일 |
|---|---|
| "이 숫자가 뭐야 / 왜 이래", 화면 설명, 특정 영역 수정 | 아래 **화면 지도**에서 해당 탭 문서 + 캡처 |
| 데이터 흐름·테이블·지표 계산식·API 목록 | `references/architecture.md` |
| 채널 연결(키 발급 안내), 연결이 안 됨 | `references/channels.md` |
| 수집·백필·배포, "데이터가 안 들어와", DB 용량 | `references/operations.md` |
| 새 업체에 처음부터 구축, 다른 업체로 복제 | `references/build-procedure.md` |
| 그래프·탭·채널을 새로 추가 | `references/architecture.md` 의 "새로 추가할 때" + 해당 탭 문서 |
| 캡처 전체 목록 · 어떤 화면이 어디 찍혀 있나 | `references/screens-index.md` |
| 최근에 무엇이 바뀌었나 | `references/changelog.md` |

## 화면 지도 (8탭)

모든 탭 위에는 공통 영역(헤더·오늘의 브리핑·기간 선택)이 있다 → `references/common-ui.md`

| 탭 | 무엇을 보는가 | 문서 | 전체 캡처 |
|---|---|---|---|
| 카페24 어드민 | 매출·주문·객단가·방문·전환, 카테고리·베스트 상품, 접속통계 | `references/tab-ops.md` | `screens/ops-00-full.png` |
| 광고 | 채널별 광고비·ROAS·전환, 채널별 30일 흐름 | `references/tab-ads.md` | `screens/ads-00-full.png` |
| 광고 히스토리 | 채널별 캠페인 성과 표, Meta·구글·카카오 소재 카드(이미지), 네이버 키워드·플레이스 | `references/tab-history.md` | `screens/hist-0*.png` |
| 유입·구매 경로(GA4) | 사이트 지표, 구매 퍼널 단계별 이탈, 매체별 유입 | `references/tab-ga4.md` | `screens/ga4-0*.png` |
| 경쟁사 모니터링 | 경쟁사 딥링크, 네이버 검색 트렌드 | `references/tab-comp.md` | `screens/comp-01-directory_trend.png` |
| 주간 리포트 · 월간 리포트 | 이전 기간 비교 리포트 + 섹션별 코멘트 + Word·Excel·PDF 다운로드 | `references/tab-reports.md` | `screens/weekly-00-full.png` |
| 채널 연결 | 채널별 연결 상태, 필요한 키, 수집 로그 | `references/tab-channels.md` | `screens/channels-01-cards.png` |

탭 문서는 영역마다 같은 형식이다: **캡처 → 보여주는 것 → 데이터 출처 → 계산 → 코드 위치 → 주의**.
캡처를 볼 때는 Read 도구로 `references/screens/<파일>.png` 를 연다. 전체 캡처(`*-00-full.png`)는 배치만 보는 용도이고, 숫자·글자는 영역 캡처에서 읽는다.

## 핵심 원칙 (왜 이렇게 만들었는지)

수정하거나 설명할 때 이 다섯 가지를 지키면 대부분의 사고를 피한다.

1. **키가 없는 채널은 자동으로 건너뛴다.** 채널 하나만 연결해도 그 채널만 수집된다. 그래서 채널을 쉬운 것부터 하나씩 붙일 수 있다.
2. **합산한 뒤에 비율을 다시 계산한다.** ROAS·전환율·객단가·CTR 같은 비율은 날짜별 값을 더하거나 평균 내면 틀린다. 합산 가능한 값(매출·주문·클릭…)만 더하고 비율은 `derive()` 로 다시 구한다.
3. **성공한 수집만 덮어쓴다.** 수집이 일부 실패하면 기존 데이터를 지우지 않고 받은 것만 덧쓴다. 빈 결과로 멀쩡한 데이터를 지우지 않기 위해서다.
4. **토큰은 DB가 우선이다.** 카페24·카카오·구글 토큰은 갱신될 때마다 DB(`app_kv`)에 다시 저장한다. GitHub Actions 러너는 매번 초기화되므로 외부 DB가 없으면 갱신된 토큰을 잃는다.
5. **날짜는 한국 시간(KST) 기준이다.** 러너는 UTC라서 그대로 쓰면 하루가 통째로 빠진다.

## 사용자와 일할 때

이 대시보드의 사용자는 개발자가 아닌 마케터·운영자다.

- 가이드는 **한 채널씩, 번호 붙인 순서로, 복사해서 붙여넣을 값과 링크를 함께** 준다. 한꺼번에 여러 채널을 안내하지 않는다.
- 사용자가 화면 캡처를 보내면 그 화면에서 **무엇을 누르고 무엇을 입력하는지**를 바로 답한다.
- 수집·백필·배포는 사용자에게 시키지 말고 직접 실행한다(`references/operations.md`). 사용자가 직접 해야 하는 것은 외부 서비스 로그인·키 발급·GitHub Secrets 입력뿐이다.
- 비밀 값(키·토큰)은 절대 저장소에 커밋하지 않는다. `config/secrets.env` 는 gitignore 대상이고, 운영 값은 GitHub Secrets 에 둔다.
- 저장소가 공개(Public)면 Actions 로그도 공개다. 진단 로그에 매출·광고비 금액을 찍지 말고 건수·구조만 찍는다.
- 화면을 고친 뒤에는 데모 데이터로 정적 페이지를 만들어 Playwright 로 직접 확인한다(가로 넘침 없음, 콘솔 오류 0). 실제 데이터 화면을 못 봤으면 못 봤다고 말한다.

## 빠른 명령

```bash
# 데모 데이터로 틀 확인 (키 불필요)
.venv/bin/python scripts/run_all.py --reset --mode demo --days 75
DASHBOARD_PASSWORD= .venv/bin/python scripts/export_static.py --out dist/index.html

# 테스트
.venv/bin/python -m pytest -q

# 실수집 (GitHub Actions) — 2025-01-01부터 전체
gh api -X POST repos/<owner>/<repo>/actions/workflows/daily-collect.yml/dispatches \
  -f ref=main -f 'inputs[from_date]=2025-01-01'

# 대시보드 재배포
gh api -X POST repos/<owner>/<repo>/actions/workflows/pages-deploy.yml/dispatches -f ref=main
```

자세한 운영 절차와 주의점은 `references/operations.md`.
