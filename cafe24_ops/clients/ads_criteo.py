"""Criteo Marketing API — 일자별 광고비·노출·클릭·전환·매출 (무료, 광고주 본인 계정).

필요: CRITEO_CLIENT_ID, CRITEO_CLIENT_SECRET  (partners.criteo.com 개발자 대시보드 → 앱 생성(Client Credentials, Marketing Solutions) → 동의 URL 생성 → 광고주 계정 관리자 승인)
선택: CRITEO_ADVERTISER_ID (비우면 접근 가능한 전체 광고주 합산)
인증: OAuth2 client_credentials → https://api.criteo.com/oauth2/token (액세스 토큰 15분)
리포트: POST /{version}/statistics/report (dimensions Day, metrics Displays/Clicks/AdvertiserCost/SalesAllPc30d/RevenueGeneratedAllPc30d)
실 키로 첫 1회 응답 필드 검증 권장. 버전은 CRITEO_API_VERSION 으로 변경 가능.
"""
from __future__ import annotations

import csv
import io
from typing import Any

import requests

from .. import config

REQUIRED_ENV = ("CRITEO_CLIENT_ID", "CRITEO_CLIENT_SECRET")
HOST = "https://api.criteo.com"
# 크리테오는 1·7월에 새 버전, 각 버전 12개월 지원 → 설정 버전이 종료(404)면 다음 후보로 자동 전환
VERSIONS = ("2026-07", "2026-01", "2027-01", "2027-07")
_ok_version = [""]


def is_configured() -> bool:
    return config.env_all(*REQUIRED_ENV)


class CriteoClient:
    def __init__(self):
        self.version = config.env("CRITEO_API_VERSION")
        r = requests.post(f"{HOST}/oauth2/token", data={
            "grant_type": "client_credentials", "client_id": config.env("CRITEO_CLIENT_ID"),
            "client_secret": config.env("CRITEO_CLIENT_SECRET")}, timeout=30)
        if r.status_code >= 400:
            raise PermissionError(f"Criteo 토큰 발급 실패 {r.status_code}: {r.text[:200]}")
        self.token = r.json()["access_token"]
        self.advertiser_id = config.env("CRITEO_ADVERTISER_ID")

    def _report(self, start: str, end: str) -> list[dict[str, str]]:
        """일별 리포트 원본 행. 실제 응답은 **BOM + 세미콜론 구분** CSV 다 (문서의 쉼표 예시와 다름 — 쉼표로 읽으면 전부 0)."""
        body: dict[str, Any] = {
            "startDate": f"{start}T00:00:00Z", "endDate": f"{end}T00:00:00Z", "timezone": "Asia/Seoul", "currency": "KRW",
            "dimensions": ["Day"], "format": "csv",
            "metrics": ["Displays", "Clicks", "AdvertiserCost", "SalesAllPc30d", "RevenueGeneratedAllPc30d"],
        }
        if self.advertiser_id:
            body["advertiserIds"] = self.advertiser_id
        r = None
        for ver in dict.fromkeys([v for v in (self.version, _ok_version[0]) if v] + list(VERSIONS)):
            r = requests.post(f"{HOST}/{ver}/statistics/report", json=body,
                              headers={"Authorization": f"Bearer {self.token}", "Accept": "text/csv"}, timeout=60)
            if r.status_code in (404, 410):
                continue  # 종료됐거나 아직 없는 API 버전 → 다음 후보
            _ok_version[0] = ver
            break
        if r.status_code in (401, 403):
            raise PermissionError(f"Criteo 권한 오류: {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"Criteo report {r.status_code}: {r.text[:300]}")
        return parse_report(r.content)

    def range_by_day(self, start: str, end: str) -> dict[str, dict[str, float]]:
        """{날짜: 5지표} — 여러 날을 한 번에 (백필은 하루씩 부르지 않는다)."""
        out: dict[str, dict[str, float]] = {}
        for row in self._report(start, end):
            day = _day(row.get("Day", ""))
            if not day:
                continue
            a = out.setdefault(day, {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0})
            a["impressions"] += _num(row.get("Displays")); a["clicks"] += _num(row.get("Clicks")); a["ad_cost"] += _num(row.get("AdvertiserCost"))
            a["conversions"] += _num(row.get("SalesAllPc30d")); a["ad_revenue"] += _num(row.get("RevenueGeneratedAllPc30d"))
        return out

    def daily(self, d: str) -> dict[str, float]:
        """하루치. 처음 요청된 날부터 60일 구간을 한 번에 받아 실행 중 기억한다."""
        key = (config.env("CRITEO_CLIENT_ID"), self.advertiser_id)
        cache = _DAYS.setdefault(key, {})
        if d not in cache:
            from datetime import date as _date, timedelta
            from ..pipeline import yesterday
            end = max(min(_date.fromisoformat(d) + timedelta(days=WINDOW - 1), _date.fromisoformat(yesterday())), _date.fromisoformat(d))
            got = self.range_by_day(d, end.isoformat())
            x = _date.fromisoformat(d)
            while x <= end:  # 응답에 없는 날 = 집행 없음(0)
                cache[x.isoformat()] = got.get(x.isoformat(), {"ad_cost": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "ad_revenue": 0.0})
                x += timedelta(days=1)
        return cache[d]


WINDOW = 60
_DAYS: dict[tuple, dict[str, dict[str, float]]] = {}


def parse_report(content: bytes | str) -> list[dict[str, str]]:
    """BOM 제거 + 구분자 자동 판별(세미콜론·쉼표·탭)."""
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content.lstrip("\ufeff")
    head = text.split("\n", 1)[0]
    delim = max((";", ",", "\t"), key=head.count)
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(io.StringIO(text), delimiter=delim)]


def _num(v: Any) -> float:
    s = str(v or "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." not in s:  # 소수점이 쉼표인 표기
        s = s.replace(",", ".")
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return 0.0


def _day(v: str) -> str:
    """리포트의 날짜를 YYYY-MM-DD 로 (ISO · 시각 포함 · M/D/YYYY · YYYYMMDD 허용)."""
    from datetime import datetime
    v = (v or "").strip()
    for fmt, n in (("%Y-%m-%d", 10), ("%Y/%m/%d", 10), ("%Y%m%d", 8)):
        try:
            return datetime.strptime(v[:n], fmt).date().isoformat()
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m/%d/%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(v.split(" ")[0] if " " in v and "%H" not in fmt else v, fmt).date().isoformat()
        except ValueError:
            pass
    return ""
