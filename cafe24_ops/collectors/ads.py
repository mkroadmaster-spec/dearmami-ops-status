"""광고 수집기 — Meta·네이버SA(파워링크/플레이스)·카카오·구글. 자격증명 있는 채널만.

한 채널 실패는 부분 실패(다른 채널 데이터는 저장). 전부 실패면 예외."""
from __future__ import annotations

from typing import Any, Callable

from ..clients import ads_google, ads_kakao, ads_meta, ads_naver
from .base import Fact, PartialFailure, fact

METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")


def _emit(d: str, channel: str, agg: dict[str, Any]) -> list[Fact]:
    return [fact(d, "ads", m, agg.get(m, 0), channel=channel) for m in METRICS]


def active_channels() -> list[str]:
    chans = []
    if ads_meta.is_configured():
        chans.append("meta")
    if ads_naver.is_configured():
        chans.append("naver_sa")
    if ads_kakao.is_configured():
        chans.append("kakao")
    if ads_google.is_configured():
        chans.append("google")
    return chans


def is_configured() -> bool:
    return bool(active_channels())


def collect(store, d: str) -> list[Fact]:
    out: list[Fact] = []
    errors: list[str] = []
    jobs: list[tuple[str, Callable[[], list[Fact]]]] = []

    if ads_meta.is_configured():
        def _meta() -> list[Fact]:
            m = ads_meta.MetaAdsClient(store)
            m.try_extend_token()
            return _emit(d, "meta", m.account_insights(d))
        jobs.append(("meta", _meta))
    if ads_naver.is_configured():
        def _naver() -> list[Fact]:
            res = ads_naver.NaverSAClient().daily_by_type(d)
            facts: list[Fact] = []
            for ch in ("naver_powerlink", "naver_place"):
                if ch in res:
                    facts += _emit(d, ch, res[ch])
            return facts
        jobs.append(("naver_sa", _naver))
    if ads_kakao.is_configured():
        jobs.append(("kakao", lambda: _emit(d, "kakao", ads_kakao.KakaoMomentClient().account_report(d))))
    if ads_google.is_configured():
        jobs.append(("google", lambda: _emit(d, "google", ads_google.GoogleAdsClient().daily(d))))

    for name, job in jobs:
        try:
            out += job()
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")

    if errors and not out:
        raise RuntimeError("ads 전부 실패: " + " | ".join(errors))
    if errors:
        raise PartialFailure(out, errors)
    return out
