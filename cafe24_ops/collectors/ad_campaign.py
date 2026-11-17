"""캠페인별 광고 성과 수집기 — 광고 히스토리 '캠페인별 성과'. source='ad_campaign', dims: channel · campaign_id · campaign.

소재·키워드 수집은 하루 상한(상위 N개)이 있어 캠페인 합계로 쓰면 모자란다 → 캠페인 단위를 따로 받는다.
  네이버: 채널 합계(ads)와 같은 /stats 호출 재사용 · 구글: GAQL campaign 30일 묶음 · 카카오: 소재 수집의 캠페인 리포트 재사용
한 채널이 실패해도 나머지는 저장(부분 실패)."""
from __future__ import annotations

from datetime import date as _date, timedelta

from ..clients import ads_google, ads_kakao, ads_naver
from .base import Fact, PartialFailure, fact

SRC = "ad_campaign"
METRICS = ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")
WINDOW = 30
_g_cache: dict[str, list[dict]] = {}


def is_configured() -> bool:
    return ads_naver.is_configured() or ads_google.is_configured() or ads_kakao.is_configured()


def _emit(d: str, channel: str, rows: list[dict]) -> list[Fact]:
    out: list[Fact] = []
    for r in rows:
        if r.get("impressions", 0) <= 0:
            continue
        dims = {"channel": channel, "campaign_id": str(r.get("campaign_id", "")), "campaign": r.get("campaign", "")}
        out += [fact(d, SRC, k, r[k], **dims) for k in METRICS if k == "impressions" or r.get(k)]  # 0 지표 생략
    return out


def _google(store, d: str) -> list[dict]:
    if d not in _g_cache:
        from ..pipeline import yesterday
        end = max(min(_date.fromisoformat(d) + timedelta(days=WINDOW - 1), _date.fromisoformat(yesterday())), _date.fromisoformat(d))
        day = _date.fromisoformat(d)
        while day <= end:
            _g_cache[day.isoformat()] = []
            day += timedelta(days=1)
        for r in ads_google.GoogleAdsClient(store).campaign_rows(d, end.isoformat()):
            _g_cache.setdefault(r["date"], []).append(r)
    return _g_cache.pop(d, [])


def collect(store, d: str) -> list[Fact]:
    out: list[Fact] = []
    errors: list[str] = []
    if ads_naver.is_configured():
        try:
            rows = ads_naver.NaverSAClient().campaign_stats(d)
            for ch in ("naver_powerlink", "naver_place"):
                out += _emit(d, ch, [r for r in rows if r["channel"] == ch])
        except Exception as e:  # noqa: BLE001
            errors.append(f"naver: {e}")
    if ads_google.is_configured():
        try:
            out += _emit(d, "google", _google(store, d))
        except PermissionError as e:
            if "최초 발급" not in str(e):
                errors.append(f"google: {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"google: {e}")
    if ads_kakao.is_configured():
        try:
            from . import kakao_creative
            out += _emit(d, "kakao", kakao_creative.campaign_rows(store, d))
        except PermissionError as e:
            if "최초 발급" not in str(e):
                errors.append(f"kakao: {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"kakao: {e}")
    if errors and not out:
        raise RuntimeError("ad_campaign 전부 실패: " + " | ".join(errors))
    if errors:
        raise PartialFailure(out, errors)
    return out
