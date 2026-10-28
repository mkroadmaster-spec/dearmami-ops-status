"""GA4 Data API (runReport) — 방문자(totalUsers)·신규/재방문·전환·세션·체류·매체별·인기 페이지.

필요: GA4_PROPERTY_ID(숫자만), GOOGLE_APPLICATION_CREDENTIALS_JSON(서비스계정 키 JSON 전체).
GCP 에서 "Google Analytics Data API" 사용설정 + 서비스계정을 GA4 속성 '뷰어'로 추가 (docs/GA4-SETUP.md).
함정: keyEvents 와 conversions 는 동일 지표 → 한 요청에 같이 넣으면 400 (keyEvents → 실패 시 conversions 폴백).
"""
from __future__ import annotations

import json
from typing import Any

from .. import config

REQUIRED_ENV = ("GA4_PROPERTY_ID", "GOOGLE_APPLICATION_CREDENTIALS_JSON")
SCOPE = ["https://www.googleapis.com/auth/analytics.readonly"]


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


class GA4Client:
    def __init__(self):
        from google.oauth2 import service_account  # type: ignore
        from google.auth.transport.requests import AuthorizedSession  # type: ignore

        info = json.loads(config.env("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPE)
        self.session = AuthorizedSession(creds)
        self.property_id = "".join(ch for ch in config.env("GA4_PROPERTY_ID") if ch.isdigit())

    def run_report(self, body: dict[str, Any]) -> dict[str, Any]:
        url = f"https://analyticsdata.googleapis.com/v1beta/properties/{self.property_id}:runReport"
        r = self.session.post(url, json=body, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"GA4 runReport {r.status_code}: {r.text[:300]}")
        return r.json()

    def _report_with_conv_metric(self, base: dict[str, Any]) -> dict[str, Any]:
        for conv in ("keyEvents", "conversions"):
            body = json.loads(json.dumps(base))
            body["metrics"].append({"name": conv})
            try:
                return self.run_report(body)
            except RuntimeError as e:
                if conv == "conversions" or "400" not in str(e):
                    raise
        return {}

    @staticmethod
    def _parse(data: dict[str, Any]) -> list[dict[str, Any]]:
        dims = [d["name"] for d in data.get("dimensionHeaders", [])]
        mets = [m["name"] for m in data.get("metricHeaders", [])]
        out = []
        for row in data.get("rows", []):
            r = {k: v["value"] for k, v in zip(dims, row.get("dimensionValues", []))}
            r.update({k: float(v["value"] or 0) for k, v in zip(mets, row.get("metricValues", []))})
            out.append(r)
        return out

    def site_daily(self, d: str) -> dict[str, float]:
        base = {"dateRanges": [{"startDate": d, "endDate": d}],
                "metrics": [{"name": "totalUsers"}, {"name": "sessions"}, {"name": "screenPageViews"},
                            {"name": "averageSessionDuration"}]}
        rows = self._parse(self._report_with_conv_metric(base))
        r = rows[0] if rows else {}
        return {"visitors": r.get("totalUsers", 0.0), "sessions": r.get("sessions", 0.0),
                "pageviews": r.get("screenPageViews", 0.0), "avg_session_sec": r.get("averageSessionDuration", 0.0),
                "conversions": max(r.get("keyEvents", 0.0), r.get("conversions", 0.0))}

    def new_vs_returning(self, d: str) -> dict[str, float]:
        rows = self._parse(self.run_report({"dateRanges": [{"startDate": d, "endDate": d}],
                                            "dimensions": [{"name": "newVsReturning"}],
                                            "metrics": [{"name": "totalUsers"}]}))
        out = {"new": 0.0, "returning": 0.0}
        for r in rows:
            if r.get("newVsReturning") in out:
                out[r["newVsReturning"]] += r["totalUsers"]
        return out

    def by_source_medium(self, d: str) -> list[dict[str, Any]]:
        base = {"dateRanges": [{"startDate": d, "endDate": d}], "dimensions": [{"name": "sessionSourceMedium"}],
                "metrics": [{"name": "sessions"}, {"name": "totalUsers"}], "limit": 50}
        return [{"source_medium": r["sessionSourceMedium"], "sessions": r["sessions"], "users": r.get("totalUsers", 0.0),
                 "conversions": max(r.get("keyEvents", 0.0), r.get("conversions", 0.0))}
                for r in self._parse(self._report_with_conv_metric(base))]

    def top_pages(self, d: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._parse(self.run_report({"dateRanges": [{"startDate": d, "endDate": d}],
                                            "dimensions": [{"name": "pagePath"}],
                                            "metrics": [{"name": "screenPageViews"}, {"name": "totalUsers"}],
                                            "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
                                            "limit": limit}))
        return [{"path": r["pagePath"], "pageviews": r["screenPageViews"], "users": r["totalUsers"]} for r in rows]


    # 구매 퍼널 이벤트 (유입·구매 경로 탭): 페이지 조회 → 상품 탐색 → 바로구매 클릭 → 장바구니 담기 → 장바구니 확인 → 구매하기 클릭 → 결제 완료
    FUNNEL_EVENTS = ("page_view", "view_item", "click_buy_now", "add_to_cart", "view_cart", "begin_checkout", "purchase")

    def event_counts(self, d: str) -> dict[str, float]:
        rows = self._parse(self.run_report({"dateRanges": [{"startDate": d, "endDate": d}],
                                            "dimensions": [{"name": "eventName"}],
                                            "metrics": [{"name": "eventCount"}], "limit": 200}))
        return {r["eventName"]: r["eventCount"] for r in rows}


FUNNEL_STEPS = [("page_view", "페이지 조회"), ("view_item", "상품 탐색"), ("click_buy_now", "바로구매 클릭"),
                ("add_to_cart", "장바구니 담기"), ("view_cart", "장바구니 확인"), ("begin_checkout", "구매하기 클릭"),
                ("purchase", "결제 완료")]


# GA4 source/medium → 광고 채널 매핑 (광고 탭 전환수 GA4 대체용)
def channel_of(source_medium: str) -> str:
    s = source_medium.lower()
    if "facebook" in s or "instagram" in s or s.startswith("fb") or "meta" in s:
        return "meta"
    if "naver" in s and ("cpc" in s or "sa" in s or "powerlink" in s):
        return "naver_powerlink"
    if "google" in s and ("cpc" in s or "paid" in s):
        return "google"
    if "kakao" in s:
        return "kakao"
    return "other"
