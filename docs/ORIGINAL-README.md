# keek 대시보드 + SNS 자동운영 — 스킬·문서 묶음

## 사용법
1. `skills/` 폴더 3개를 새 프로젝트의 `.claude/skills/` 아래에 그대로 복사
   - 카페24-운영현황  : 운영현황 대시보드(A)
   - 온라인-광고      : 광고 대시보드(B)
   - sns-auto-operation : SNS 자동운영(C)
2. `docs/NEW-CLIENT-CHECKLIST.md` 부터 읽고 순서대로 진행
3. 나머지 docs 는 체크리스트에서 참조하는 상세 가이드

## docs
- NEW-CLIENT-CHECKLIST.md : 이식 체크리스트(진입점) — 계정·토큰·Secret·코드 치환·사고 사례
- CONNECT-GUIDE.md        : 카페24 앱 등록·토큰 발급
- TOKEN-LOCATIONS.md      : 채널별 토큰이 어디 있는지
- SECURITY-ROTATION.md    : 키 재발급·회전 절차 (Meta 만료 복구 포함)
- DEPLOY-FREE.md          : Neon + Render 무료 배포
- GA4-SETUP.md            : GA4 서비스계정 연동
- GITHUB-ACTIONS.md       : 수집 크론·워크플로
