"""광고 수집기 — Meta·네이버SA(파워링크/플레이스)·카카오·구글. 자격증명 있는 채널만.

한 채널 실패는 부분 실패(다른 채널 데이터는 저장). 전부 실패면 예외."""
from __future__ import annotations

from typing import Any, Callable

from .. import config
from ..clients import ads_criteo, ads_gfa, ads_google, ads_kakao, ads_meta, ads_naver, manual_csv
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
    if ads_criteo.is_configured():
        chans.append("criteo")
    if ads_gfa.is_configured():
        chans.append("gfa")
    chans += [f"csv:{c}" for c in manual_csv.channels() if not (c == "gfa" and ads_gfa.is_configured())]
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
        jobs.append(("kakao", lambda: _emit(d, "kakao", ads_kakao.KakaoMomentClient(store).account_report(d))))
    if ads_google.is_configured():
        jobs.append(("google", lambda: _emit(d, "google", ads_google.GoogleAdsClient(store).daily(d))))
    if ads_criteo.is_configured():
        jobs.append(("criteo", lambda: _emit(d, "criteo", ads_criteo.CriteoClient().daily(d))))
    if ads_gfa.is_configured():
        jobs.append(("gfa", lambda: _emit(d, "gfa", ads_gfa.GfaClient(store).daily(d))))
    for ch in manual_csv.channels():  # CSV 업로드 채널 (GFA·모비온 등) — 해당 날짜 행이 있을 때만
        if ch == "gfa" and ads_gfa.is_configured():
            continue  # API 연결 후에는 CSV 보다 API 우선
        row = manual_csv.day(ch, d)
        if row:
            out += _emit(d, ch, row)

    only = {s.strip() for s in config.env("ADS_ONLY").split(",") if s.strip()}
    if only:  # 특정 채널만 백필 (예: ADS_ONLY=naver_sa) — 나머지 채널 API 호출 생략
        jobs = [(n, j) for n, j in jobs if n in only]
        out = [f for f in out if f.get("dims", {}).get("channel") in only]

    for name, job in jobs:
        try:
            out += job()
        except PermissionError as e:
            if "최초 발급" in str(e):  # 최초 토큰 발급 전에만 스킵 (리프레시 토큰 유실·갱신 실패는 오류로 표시)
                continue
            errors.append(f"{name}: {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")

    if errors and not out:
        raise RuntimeError("ads 전부 실패: " + " | ".join(errors))
    if errors:
        raise PartialFailure(out, errors)
    return out
