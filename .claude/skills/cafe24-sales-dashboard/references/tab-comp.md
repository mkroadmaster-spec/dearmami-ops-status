# 탭 5 · 경쟁사 모니터링 (`#comp`)

캡처: `screens/comp-01-directory_trend.png` · 화면 코드: `section#tab-comp` + `loadComp()`

## 1. 지정 현황 딥링크

- **보여주는 것**: 경쟁사마다 한 줄 — 홈페이지 · 인스타그램 · FB 광고 라이브러리(집행 중 광고) · 구글 광고 투명성 센터 링크
- **출처**: `/api/competitors/directory` → `breakdown.competitor_directory()`. 데이터 수집이 아니라 **링크를 만들어 주는 것**이다.
- **설정**: `config/sources.yaml` 의 `competitors[]` (`name`, `url`, `insta`, `domain`, `fb_query`). 비워 두면 이름으로 검색 링크를 자동 생성한다.
- **왜 링크만인가**: 경쟁사의 광고비·성과는 어떤 무료 API 로도 얻을 수 없다. 공개된 광고 라이브러리를 바로 열 수 있게 해 주는 것이 무료로 할 수 있는 최선이다. 사용자가 "경쟁사 광고비를 보여 달라"고 하면 불가능하다고 분명히 말한다.

## 2. 네이버 검색 트렌드

- **보여주는 것**: 자사 브랜드와 경쟁사 이름의 네이버 검색량 추이 선 그래프 (선택 기간)
- **출처**: `/api/competitors/trend` → `breakdown.competitor_trend()` — facts `competitor` (네이버 데이터랩 검색어 트렌드 API)
- **필요한 키**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (developers.naver.com 애플리케이션, 데이터랩 검색어 트렌드 사용 설정)
- **주의**:
  - 값은 **0~100 상대지수**다. 절대 검색량이 아니다. 조회한 키워드들 가운데 가장 높은 지점이 100 이다.
  - 키워드는 최대 5개(자사 포함).
  - 키가 없으면 "네이버 오픈API 미연결" 안내가 나온다.
