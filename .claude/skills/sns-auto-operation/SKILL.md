---
name: sns-auto-operation
description: >-
  SNS 채널 자동 운영 시스템 — 브랜드/업체의 SNS(인스타그램·스레드·구글블로그·네이버블로그·유튜브·링크드인)를
  24시간 무인 자동 운영하는 시스템을 새 업체에 세팅할 때 사용. 매일 정해진 시각 자동발행,
  AI(클로드) 글 생성, 한글 카드/블로그 이미지 렌더, 유튜브 쇼츠 모션영상(힉스필드)+무료 BGM,
  실시간 대시보드(GitHub Pages), 성과 자체학습 선순환까지 포함. "다른 업체에도 적용", "새 클라이언트
  SNS 자동화 세팅", "SNS 무인 운영 붙여줘" 같은 요청에 사용.
---

# SNS 채널 자동 운영 시스템 (SNS Auto-Operation System)

브랜드 하나의 SNS를 **무료로 24시간 무인 운영**하는 완성형 시스템. 이 저장소(`pslab`)가
레퍼런스 구현이며, 아래 절차대로 **새 업체(client)를 추가**하면 그대로 재사용된다.

> 핵심 철학: **대시보드가 곧 제품이다.** 모든 작업 결과는 대시보드(GitHub Pages)에서
> 링크로 확인 가능해야 한다. 비개발자 담당자를 위해 설명은 **쉬운 한국어**로.

---

## 1. 아키텍처 (무엇인가)

- **언어/런타임**: TypeScript ESM, Node 20+. import에 `.js` 확장자 사용.
- **채널 플러그인 구조**: `src/plugins/*` (BasePlugin → PluginRegistry → Publisher). 채널 추가 = 플러그인 추가.
- **무료 24시간 호스팅**: GitHub Actions cron(무인 루프) + GitHub Pages(`docs/`)로 대시보드 배포.
- **콘텐츠 생성**:
  - 글: 클로드 API(`src/core/claude.ts`) — 키 없으면 규칙기반 폴백.
  - 이미지: **HTML→Chromium 스크린샷**으로 렌더(`scripts/render-*.mjs`). AI 확산모델은 한글을 깨뜨리므로 텍스트는 반드시 HTML로.
  - 유튜브 쇼츠: 힉스필드 모션클립 배경 + 한글 투명 오버레이 + 무료 BGM(`scripts/render-shorts.mjs`, `build-shorts-video.mjs`).
- **자체 학습 선순환**: 발행 → 반응 수집(`collect-insights`) → `learning.json` → 다음 기획에 디자인/주제/시간대 반영.
- **멀티 클라이언트**: 모든 데이터는 `data/clients/<clientId>/` 아래. 코드/스크립트/워크플로는 공유.

### 채널별 자동화 가능 여부 (정직하게)
| 채널 | 자동발행 | 방식 |
|---|---|---|
| 인스타그램 | ✅ | Instagram Graph API (캐러셀) |
| 스레드 | ✅ | Threads API |
| 구글 블로그 | ✅ | Blogger API v3 (OAuth2 refresh token) |
| 링크드인 | ✅ | LinkedIn API |
| 네이버 블로그 | ❌ 수동 | 공식 발행 API 없음 → 대시보드에서 본문 복사 + 이미지 다운로드 |
| 유튜브 | ❌ 수동 | 미검증 앱 업로드는 비공개 고정 → 영상 다운로드 + 제목/설명/태그 복사 |

---

## 2. 재사용 자산 (이 저장소의 파일 지도)

**코어** (`src/core/`): `client.ts`(클라이언트 로드), `plan.ts`(기획안 저장/상태), `publisher.ts`,
`registry.ts`, `plugin.ts`, `claude.ts`(AI 글), `generate.ts`(기획 생성 + 학습 반영),
`insight.ts`(성과 수집), `learning.ts`(자체학습), `dashboard.ts`(상황판 HTML), `notify.ts`(텔레그램),
`weekly.ts`(주간리포트), `token-health.ts`(토큰 만료 점검).

**채널 플러그인** (`src/plugins/`): `instagram.ts`, `threads.ts`, `blogger.ts`, `linkedin.ts`,
`naver-blog.ts`, `youtube.ts`, `shared.ts`.

**렌더/미디어 스크립트** (`scripts/`): `render-cards.mjs`(인스타 캐러셀), `render-blog-images.mjs`,
`render-shorts.mjs`(쇼츠 슬라이드+투명 오버레이), `build-shorts-video.mjs`(부메랑 배경+오버레이+BGM),
`fetch-photos.mjs`(배경 사진 CI 다운로드), `seed-*.mjs`(초기 콘텐츠 시드), `schedule-daily.mjs`(일일 재배치).

**워크플로** (`.github/workflows/`): `pslab-cron.yml`(무인 루프+Pages 배포), `pslab-publish.yml`,
`pages-deploy.yml`(docs/ 배포).

**클라이언트 데이터** (`data/clients/<id>/`): `plan.json`(기획안), `design.json`, `learning.json`,
`bg-sources.json`(힉스필드 배경 URL), `video-sources.json`(쇼츠 모션클립 URL),
`weekly-reports.json`, `token-health.json`.

---

## 3. 새 업체(client) 온보딩 — 단계별

> 같은 저장소에 client를 추가하거나(간단), 이 저장소를 통째로 복제해 별도 배포(완전 분리)도 가능.
> **업체별로 브랜드·콘텐츠·성과가 완전히 섞이지 않아야 함** (과거 다른 프로젝트가 같은 repo/Pages를
> 공유해 배포 충돌 난 사례 있음 → §8 참고).

1. **브랜드 정보 수집**: 브랜드명, 톤, 핵심 주제, 타깃, 채널 계정, 발행 시각(예: 매일 18시).
2. **클라이언트 설정 생성**: `data/clients/<id>/`에 클라이언트 config + `design.json` 팔레트.
   기존 `demo-cafe`/`pslab`을 템플릿으로 복사해 값만 교체. `normalizeClientConfig`는 `reviewMode`
   필드가 필요하니 누락 금지.
3. **초기 기획안 생성**: `seed-plan.mjs`/`generate.ts`로 주제·슬라이드 생성 → `plan.json`
   (status=`planned`). 채널·주제는 브랜드에 맞게.
4. **채널 시크릿 등록**: GitHub 저장소 Settings → Secrets에 채널별 토큰(§4). **코드에 절대 넣지 말 것.**
5. **AI 글 켜기(선택)**: `ANTHROPIC_API_KEY` 시크릿 + (비용절감) Variables `PSLAB_CLAUDE_MODEL=claude-haiku-4-5`.
   없으면 규칙기반으로 안전 동작.
6. **일정 배치**: `node scripts/schedule-daily.mjs --client <id>` → 하루 1개씩 18:00 KST, 채널 라운드로빈.
   cron은 `0 9 * * *`(09:00 UTC = 18:00 KST) + `30 9 * * *` 보정.
7. **실제 발행 ON**: Variables `PSLAB_DRY_RUN=false` (기본 true = 안전 시뮬레이션).
8. **Pages 켜기**: Settings → Pages → Source = **GitHub Actions**. **무료 플랜은 public 저장소만 Pages 지원**
   (private면 404). 시크릿은 public이어도 노출 안 됨.
9. **검증**: 워크플로 수동 실행 → 대시보드(`https://<owner>.github.io/<repo>`)에서 체크리스트 5/5,
   일정, 카드/영상 확인 → 예정시각에 첫 자동발행 + 텔레그램 알림 확인.

---

## 4. 채널 연동 가이드 (담당자가 발급할 것)

각 채널 토큰을 GitHub **Secrets**에 넣는다. 이름은 `pslab-cron.yml`의 env 블록 참고.

- **인스타그램/스레드**: Meta 개발자 앱 → 페이지/IG 비즈니스 계정 연결 → 장기 액세스 토큰.
  `PSLAB_INSTAGRAM_ACCESS_TOKEN`, `PSLAB_INSTAGRAM_IG_USER_ID`, `PSLAB_THREADS_ACCESS_TOKEN`,
  `PSLAB_THREADS_THREADS_USER_ID`. (앱ID/시크릿 넣으면 토큰 만료일 계산·경고 가능)
- **구글 블로그(Blogger)**: Google Cloud 프로젝트 → Blogger API 활성화 → OAuth 클라이언트 →
  OAuth Playground로 `refresh_token` 발급. `PSLAB_BLOGGER_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/BLOG_ID`.
- **링크드인**: `PSLAB_LINKEDIN_ACCESS_TOKEN`, `PSLAB_LINKEDIN_AUTHOR_URN`.
- **텔레그램 알림**: @BotFather로 봇 생성 → `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- **네이버·유튜브**: 자동발행 불가(위 표). 대시보드 복사/다운로드 도우미로 담당자가 직접 게시.
- **AI/이미지**: `ANTHROPIC_API_KEY`(글). 배경 실사진(선택) `PEXELS_API_KEY`.

담당자 가이드는 항상 **화면 캡처를 요청받으면 어디를 누를지 짚어주는** 방식으로. `오픈-가이드.md`,
`구글블로그-연동.md` 같은 문서를 업체별로 만들어 두면 좋다.

---

## 5. 콘텐츠 파이프라인 상세

- **AI 글**: `claude.ts`가 `PSLAB_CLAUDE_MODEL`(기본 opus, 비용은 haiku) 사용. 크레딧 없으면 규칙기반.
- **한글 이미지**: `render-*.mjs`가 HTML+Pretendard(base64 인라인) → Chromium `--screenshot`.
  세이프존: 쇼츠는 상단 320/하단 480 피해 중앙 밴드. **AI 이미지로 한글 텍스트를 만들지 말 것.**
- **인물·배경 사진**: 힉스필드(`soul_2`, 9:16)로 장면 생성 → URL을 `bg-sources.json`에 저장 →
  **CI에서 다운로드**(개발환경은 외부 호스트 접근 불가, cloudfront 403). `fetch-photos.mjs`가 CI에서 받음.
- **유튜브 쇼츠 모션영상**:
  1) 힉스필드 시작이미지(`soul_2`) → `kling2_6` 이미지→영상(9:16, 5초, ~10크레딧, 무음).
  2) URL을 `video-sources.json`에 저장.
  3) `render-shorts.mjs`가 투명 오버레이(`ov-N.png`, 반투명 패널) 렌더.
  4) `build-shorts-video.mjs`가 CI에서 클립 다운로드 → **부메랑(정+역) 끊김없는 배경** → 타임드 오버레이 → BGM.
  - **무료 BGM**: `assets/bgm/*.mp3` 있으면 그것, 없으면 ffmpeg 합성 앰비언트 패드(저작권 0).

---

## 6. 발행·일정·대시보드

- `publish-plan --due`: `scheduledFor <= now` 이고 status가 published/manual이 아닌 항목을 발행.
  자동채널은 실제 게시, 수동채널(네이버/유튜브)은 status=`manual`로 표시(대시보드에서 복붙).
  `PSLAB_DRY_RUN=true`면 상태 변경 없이 시뮬레이션(가짜 '발행됨' 방지).
- **일일 18시**: `schedule-daily.mjs`로 미발행 항목을 하루 1개씩 18:00 KST 재배치(채널 라운드로빈).
  cron `0 9 * * *` + `30 9 * * *`(보정). publish-plan은 멱등이라 중복발행 없음.
- **대시보드**(`dashboard.ts`): 채널현황·발행/대기·성과·오픈 체크리스트·주간리포트·네이버/유튜브 도우미.
  5분 자동 새로고침. **빈 화면 방지**: 메인 스크립트 앞 `window.onerror` + 렌더 try/catch로 오류를 화면에 표시.

---

## 7. 비용

- **거의 전부 무료**: GitHub Actions(무료 분), Pages(공개 repo), 렌더(Chromium/ffmpeg).
- **유료는 선택 요소만**: 클로드 API(하루 2회, Haiku 월 ~1~2천원 / Opus ~5~10천원),
  힉스필드 영상(편당 ~10크레딧). 콘솔에서 사용 한도 걸어두면 초과 없음.

---

## 8. 반드시 아는 함정 (하드-원 교훈)

- **개발환경은 외부 호스트 접근 불가**(cloudfront/외부 이미지 403). 미디어는 **세션에서 생성→URL 저장→
  CI에서 다운로드**. 이미지 다운로드·영상 합성은 네트워크 열린 CI(GitHub Actions)에서만.
- **한글은 HTML→Chromium**로 렌더. AI 확산 이미지에 한글 넣으면 깨진다.
- **private 저장소 = 무료 플랜에서 Pages 꺼짐(404)**. public 유지(시크릿은 안전). visibility 바꾸면
  Pages Source가 None으로 초기화되니 다시 `GitHub Actions`로 켜야 함.
- **GITHUB_TOKEN으로 push하면 다른 워크플로가 트리거되지 않음**(무한루프 방지). 그래서 각 워크플로가
  자기 배포 스텝을 가져야 하고, **Pages 배포하는 워크플로는 concurrency group을 통일**(예: `pages`)해야
  동시배포 경쟁(→404)이 안 생긴다. 여러 프로젝트가 한 repo/Pages를 공유하면 특히 주의.
- **커밋 메시지에 `[skip ci]` 금지**(Pages 배포까지 막힘).
- **동시 push 충돌**: 커밋 스텝에 `git pull --rebase` + 재시도.
- **가짜 성공 차단**: 자동발행 불가 채널은 publish에서 ok:false로. dry-run에선 상태 변경 안 함.
- **힉스필드 큐 지연** 가능(starter 플랜). 급하면 다른 모델(seedance/grok)로 재시도하되 큐가 풀리면
  추가 비용 없이 완료되기도 함.
- **AI 텍스트가 대시보드 데이터에 들어가도** JSON.stringify + `<` 이스케이프(`<`)로 안전.

---

## 9. 빠른 시작 체크리스트 (새 업체)

```
[ ] data/clients/<id>/ 설정 + design.json (템플릿 복사)
[ ] seed-plan/generate 로 plan.json 생성
[ ] 채널 토큰 → GitHub Secrets
[ ] ANTHROPIC_API_KEY (+ PSLAB_CLAUDE_MODEL=claude-haiku-4-5)
[ ] schedule-daily.mjs 로 매일 18시 배치
[ ] Variables PSLAB_DRY_RUN=false
[ ] Settings→Pages→Source=GitHub Actions (repo는 public)
[ ] 워크플로 수동 실행 → 대시보드 5/5 확인 → 첫 발행·텔레그램 확인
```
