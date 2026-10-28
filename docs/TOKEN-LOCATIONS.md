# 채널별 토큰 위치 가이드

각 `secrets.env` 변수를 **어디서 확인/발급**하는지 정리. 두 종류로 나뉩니다:
- 🔎 **조회형**: 콘솔에서 바로 복사 (Client ID/Secret, API Key, 계정 ID)
- 🔧 **발급형**: OAuth 등으로 생성해야 함 (Access/Refresh Token) — 조회만으로는 안 됨

---

## 1. 카페24 (매출·주문)
| 변수 | 종류 | 위치 |
|---|---|---|
| `CAFE24_MALL_ID` | 🔎 | 쇼핑몰 주소 `keek.cafe24.com` 의 `keek` |
| `CAFE24_CLIENT_ID` / `CAFE24_CLIENT_SECRET` | 🔎 | **developers.cafe24.com** → 내 앱 → 앱 선택 → "앱 정보/인증 정보"의 Client ID, Secret |
| `CAFE24_ACCESS_TOKEN` / `CAFE24_REFRESH_TOKEN` | 🔧 | 콘솔에 없음 → `python scripts/cafe24_auth.py` 로 OAuth 발급 |

> 앱 설정에서 Redirect URI `https://localhost`, scope `mall.read_order`,`mall.read_customer` 먼저 등록.

---

## 2. Meta (페이스북/인스타 광고)
| 변수 | 종류 | 위치 |
|---|---|---|
| `META_ACCESS_TOKEN` | 🔧 | **business.facebook.com** → 비즈니스 설정 → 사용자 → **시스템 사용자** → 토큰 생성(권한 `ads_read`). 장수명 토큰 권장 |
| `META_AD_ACCOUNT_ID` | 🔎 | **Ads Manager**(adsmanager.facebook.com) 좌상단 계정 선택 → `act_` 뒤 숫자. 또는 비즈니스 설정 → 계정 → 광고 계정 |

> 임시 테스트는 developers.facebook.com → Graph API Explorer 에서도 토큰 생성 가능(단명).

---

## 3. Google Ads
| 변수 | 종류 | 위치 |
|---|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | 🔎 | **ads.google.com**(관리자/MCC 계정) → 도구 및 설정 → 설정 → **API 센터** |
| `GOOGLE_ADS_CUSTOMER_ID` | 🔎 | Google Ads 우상단 10자리(`xxx-xxx-xxxx`, 대시 제거해 입력) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | 🔎 | MCC(관리자) 계정 ID (MCC 사용 시) |
| `GOOGLE_ADS_ACCESS_TOKEN` | 🔧 | OAuth2 로 생성 → **developers.google.com/oauthplayground** 또는 OAuth 플로우(refresh token → access token) |

> 개발자 토큰은 신청 후 "테스트 액세스"는 즉시, 운영 액세스는 승인 필요.

---

## 4. 네이버 검색광고 (SA)
| 변수 | 종류 | 위치 |
|---|---|---|
| `NAVER_SA_API_KEY` | 🔎 | **searchad.naver.com** → 로그인 → 도구 → **API 사용 관리** → 액세스 라이선스 |
| `NAVER_SA_SECRET_KEY` | 🔎 | 같은 화면의 비밀키 (발급 시 1회 노출 → 저장 필수) |
| `NAVER_SA_CUSTOMER_ID` | 🔎 | 검색광고 로그인 후 우상단 계정 정보의 **CUSTOMER_ID**(광고주 ID, 숫자) |

---

## 5. 카카오모먼트 (광고)
| 변수 | 종류 | 위치 |
|---|---|---|
| `KAKAO_ACCESS_TOKEN` | 🔧 | **developers.kakao.com** → 내 애플리케이션 → 앱 → 카카오 로그인/OAuth 로 토큰 발급(모먼트 권한) |
| `KAKAO_AD_ACCOUNT_ID` | 🔎 | **moment.kakao.com** → 광고계정 → 계정 관리에서 계정 ID(숫자) |

> 앱의 REST API 키는 developers.kakao.com → 앱 → 앱 키 에서 확인.

---

## 6. 네이버 데이터랩/검색 (경쟁사 — 무료)
| 변수 | 종류 | 위치 |
|---|---|---|
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 🔎 | **developers.naver.com** → Application → **내 애플리케이션** → 앱 선택 → 개요의 Client ID/Secret |

> 앱 등록 시 "검색"과 "데이터랩(검색어트렌드)" API 사용 추가.

---

## 7. Slack 알림 (선택 — 무료)
| 변수 | 종류 | 위치 |
|---|---|---|
| `SLACK_WEBHOOK_URL` | 🔎 | **api.slack.com/apps** → 앱 → Incoming Webhooks → Webhook URL 복사 |

---

## 정리: 콘솔에서 바로 보이는 것 vs 발급해야 하는 것
- 🔎 **바로 복사**: 카페24 Client ID/Secret·mall_id, Meta 광고계정ID, Google 개발자토큰·Customer ID,
  네이버 SA 키 3종, 카카오 광고계정ID, 네이버 Client ID/Secret, Slack Webhook
- 🔧 **발급 필요(조회 불가)**: 카페24/Meta/Google/Kakao 의 **Access/Refresh Token** — OAuth 로 생성

> 발급형 토큰은 만료가 있습니다(카페24 access 2시간·refresh 2주, Meta 시스템사용자 장수명 등).
> 카페24는 `cafe24_auth.py` 가, 나머지는 각 플랫폼 OAuth 가 발급합니다.

## 보존 위치 (재발 방지)
이 컨테이너는 매 세션 초기화되므로, 발급한 값은 **환경 설정의 시크릿/환경변수** 또는
**GitHub Secrets** 에 넣으세요. `secrets.env`(로컬)만 쓰면 세션 종료 시 사라집니다.
