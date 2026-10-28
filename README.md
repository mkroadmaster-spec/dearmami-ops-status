# cafe24-ops-status — 카페24 자사몰 매출·광고 운영현황 대시보드

카페24 매출·주문·접속통계 + GA4 사이트 분석 + Meta/네이버/카카오/구글 광고 + 소재·키워드 히스토리 + 경쟁사 트렌드를 **매일 무인 수집**해
5개 탭(**카페24 어드민 / 광고 / 광고 히스토리 / 주간 리포트(월간 포함, Word 다운로드) / 채널 연결**)으로 보여주는 무료 스택 대시보드.
`keek` 대시보드(keek-ops-dashboard)와 같은 탭·지표·리포트 시스템을 스킬 명세대로 재구현했고, 채널은 자격증명을 넣는 순서대로 하나씩 켜진다.
1차 업체: **디어마미**(dearmami.co.kr). 다른 업체 전환은 `scripts/new_client.py`, 절차는 `.claude/skills/매출-대시보드-구축`.

```
수집기(채널별, 키 없으면 자동 스킵) → facts(정규화) → kpi_daily(집계) → SQLite/Neon → FastAPI → 대시보드
```

## 빠른 시작
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./scripts/dev.sh          # 데모 30일 생성 + http://localhost:8000
```
실데이터 연결은 **[docs/SETUP-GUIDE.md](docs/SETUP-GUIDE.md)** 를 STEP 0 부터 순서대로.

## 구조
| 경로 | 역할 |
|---|---|
| `config/sources.yaml` | 업체별 값(브랜드·몰ID·광고계정·경쟁사) |
| `config/metrics.yaml` | 요약 카드·카테고리 그룹 (코드 수정 없이 변경) |
| `config/secrets.env` | 채널 자격증명 (`.example` 복사, git 제외) |
| `cafe24_ops/clients/` | 채널 API 클라이언트 9개 (cafe24, cafe24_analytics, ga4, ads_meta, ads_naver, ads_kakao, ads_google, naver_datalab, slack) |
| `cafe24_ops/collectors/` | 수집기 레지스트리 + 데모 생성기. 새 채널 = `__init__.py` 에 등록 |
| `cafe24_ops/etl/` | `aggregate.py`(kpi_daily·기간합계·비교) `breakdown.py`(기간비교·채널·접속통계 9블록·GA4 사이트·소재 피로도·키워드/플레이스) `period_report.py`(주간/월간 리포트 코어) |
| `cafe24_ops/alerts.py` · `report_docx.py` | 오늘의 브리핑 · 리포트 Word 생성 |
| `cafe24_ops/store.py` | SQLite 기본, `DATABASE_URL` 있으면 Postgres. 토큰은 `app_kv` (Secret 보다 우선) |
| `api/main.py` | FastAPI (`/health` `/api/summary` `/api/daily` `/api/digest` `/api/breakdown` `/api/ads/channels` `/api/channels` …) |
| `dashboard/index.html` | 화면 (Chart.js 는 `dashboard/vendor/` 번들 — 외부 CDN 불필요) |
| `scripts/` | `run_all.py` 수집 · `cafe24_auth.py` 토큰 · `smoke_live.py --check` 인증 확인 · `notify.py` Slack · `weekly_report.py` .docx · `export_static.py` 정적 게시 · `new_client.py` 업체 전환 · `dev.sh` |
| `.github/workflows/` | `daily-collect`(07:00 KST) · `cafe24-weekly-report`(월 08:25 KST, .docx 아티팩트) · `cafe24-authorize-url` · `cafe24-token-fast` · `cafe24-token-reset` · `api-smoke` |
| `docs/clients/<id>.md` | 업체별 온보딩 기록(담당자 발급 체크리스트) |
| `render.yaml` | Render Blueprint (무료 웹 서비스) |
| `docs/` | 원본 가이드 7종 + `SETUP-GUIDE.md`(순차 가이드) |
| `.claude/skills/` | 카페24-운영현황 · 온라인-광고 · sns-auto-operation 스킬 |

## 비밀번호 보호
`DASHBOARD_PASSWORD` 를 설정하면 서버는 `/login` 로그인(30일 쿠키), 정적 내보내기(`export_static.py`)는 스냅샷을 AES-GCM 으로 암호화해 비밀번호 없이는 열 수 없다. 비밀번호는 `secrets.env`/Render env/GitHub Secrets 에만 두고 코드에 넣지 않는다.

## 자주 쓰는 명령
```bash
.venv/bin/python scripts/run_all.py --mode demo --days 30          # 데모
.venv/bin/python scripts/smoke_live.py --check                       # 채널 인증 확인
.venv/bin/python scripts/run_all.py --reset --mode live --days 14    # 데모→실데이터 전환
.venv/bin/python scripts/run_all.py --mode live --days 3             # 일일(최근 3일 재수집)
.venv/bin/python -m pytest -q                                        # 테스트
```

## 반드시 지킬 것 (keek 사고 사례)
- 카페24 토큰은 **`Cafe24Client.from_store`** 로만 생성 (refresh 회전분 즉시 DB 저장). 회귀 테스트 `tests/test_cafe24_token_rotation.py`
- 카페24 앱 scope **7개 전부** — 빠지면 오류 없이 지표가 빈다
- Meta 는 **시스템 사용자 토큰**(만료 없음) + Slack 알림
- 무인 운영은 **Neon `DATABASE_URL` 필수** (러너 초기화 → 토큰 유실)
- 업체당 저장소 1개 분리 권장
