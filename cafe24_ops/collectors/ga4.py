"""GA4 수집기 — 한 수집기가 3개 source 를 낸다: ga4(사이트 지표) · ga4_channel(매체별) · ga4_page(인기 페이지)."""
from __future__ import annotations

from ..clients.ga4 import FUNNEL_STEPS, GA4Client, channel_of
from .base import Fact, PartialFailure, fact

SOURCES = ("ga4", "ga4_channel", "ga4_page", "ga4_event")


def collect(store, d: str) -> list[Fact]:
    g = GA4Client()
    site = g.site_daily(d)
    nr = g.new_vs_returning(d)
    out = [
        fact(d, "ga4", "visitors", site["visitors"]), fact(d, "ga4", "sessions", site["sessions"]),
        fact(d, "ga4", "pageviews", site["pageviews"]), fact(d, "ga4", "conversions", site["conversions"]),
        fact(d, "ga4", "avg_session_sec", site["avg_session_sec"]),
        fact(d, "ga4", "new_visitors", nr["new"]), fact(d, "ga4", "returning_visitors", nr["returning"]),
    ]
    errors = []
    try:
        for r in g.by_source_medium(d):
            dims = {"source_medium": r["source_medium"], "channel": channel_of(r["source_medium"])}
            out += [fact(d, "ga4_channel", "sessions", r["sessions"], **dims),
                    fact(d, "ga4_channel", "users", r["users"], **dims),
                    fact(d, "ga4_channel", "conversions", r["conversions"], **dims)]
    except Exception as e:  # noqa: BLE001
        errors.append(f"source_medium: {e}")
    try:
        for r in g.top_pages(d):
            out += [fact(d, "ga4_page", "pageviews", r["pageviews"], path=r["path"]),
                    fact(d, "ga4_page", "users", r["users"], path=r["path"])]
    except Exception as e:  # noqa: BLE001
        errors.append(f"pages: {e}")
    try:
        ev = g.event_counts(d)
        out += [fact(d, "ga4_event", "event_count", ev.get(k, 0), event=k) for k, _ in FUNNEL_STEPS]
    except Exception as e:  # noqa: BLE001
        errors.append(f"events: {e}")
    if errors:
        raise PartialFailure(out, errors)
    return out
