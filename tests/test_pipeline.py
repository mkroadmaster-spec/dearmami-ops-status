import os

import pytest

from cafe24_ops import pipeline
from cafe24_ops.collectors import REGISTRY, channel_status
from cafe24_ops.etl.aggregate import compare, kpis_from_facts, previous_range, sum_range
from cafe24_ops.store import Store

EXPECTED_SOURCES = {"cafe24", "cafe24_analytics", "ga4", "ads", "creative", "naver_keyword", "competitor"}


@pytest.fixture
def store(tmp_path):
    return Store(f"sqlite:///{tmp_path}/t.db")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith(("CAFE24_", "GA4_", "GOOGLE_", "META_", "NAVER_", "KAKAO_", "SLACK_", "TELEGRAM_", "DATABASE_URL")):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("cafe24_ops.config._loaded", True)  # secrets.env 무시


def test_registry_sources():
    assert {c.name for c in REGISTRY} == EXPECTED_SOURCES


def test_live_without_credentials_skips_everything(store):
    r = pipeline.run_day(store, "2026-10-01", mode="live")
    assert all(s["status"] == "skip" for s in r["sources"].values())
    assert r["kpi"].get("gross_sales") is None


def test_demo_populates_all_sources_and_kpis(store):
    r = pipeline.run_day(store, "2026-10-01", mode="demo")
    assert all(s["status"] == "ok" for s in r["sources"].values())
    k = r["kpi"]
    assert k["gross_sales"] > 0 and k["orders"] > 0
    assert k["aov"] == pytest.approx(k["gross_sales"] / k["orders"])
    assert k["visitors_source"] == 1  # GA4 우선
    assert k["roas"] == pytest.approx(k["ad_revenue"] / k["ad_cost"] * 100)


def test_demo_is_deterministic(store):
    a = pipeline.run_day(store, "2026-10-02", mode="demo")["kpi"]
    b = pipeline.run_day(store, "2026-10-02", mode="demo")["kpi"]
    assert a["gross_sales"] == b["gross_sales"]
    # 재수집해도 중복 집계 없음 (delete + upsert)
    assert len(store.facts("2026-10-02", "2026-10-02", source="cafe24", metric="gross_sales")) == 1


def test_visitors_fallback_to_cafe24_analytics():
    facts = [
        {"date": "d", "source": "cafe24", "metric": "orders", "value": 10, "dims": {}},
        {"date": "d", "source": "cafe24_analytics", "metric": "visit_count", "value": 500, "dims": {}},
    ]
    k = kpis_from_facts(facts)
    assert k["visitors"] == 500 and k["visitors_source"] == 0
    assert k["conversion_rate"] == pytest.approx(2.0)


def test_sum_range_recomputes_derived():
    days = {"d1": {"gross_sales": 100, "orders": 2}, "d2": {"gross_sales": 300, "orders": 2}}
    s = sum_range(days)
    assert s["gross_sales"] == 400 and s["aov"] == 100  # (100+300)/4, 파생값 합산 아님


def test_previous_range_and_compare():
    assert previous_range("2026-10-08", "2026-10-14") == ("2026-10-01", "2026-10-07")
    c = compare({"x": 120.0}, {"x": 100.0})
    assert c["x"]["pct"] == pytest.approx(20.0)


def test_channel_status_lists_all_channels(store):
    keys = {c["key"] for c in channel_status(store)}
    assert {"cafe24", "cafe24_analytics", "ga4", "meta", "naver_sa", "kakao", "google", "competitor", "slack", "telegram"} <= keys
    assert not any(c["configured"] for c in channel_status(store))


def test_kv_roundtrip(store):
    store.kv_set("k", "v")
    assert store.kv_get("k") == "v"
    store.kv_delete("k")
    assert store.kv_get("k") == ""


def test_demo_products_follow_client_categories():
    from cafe24_ops.collectors import demo
    demo.products.cache_clear()
    prods = demo.products()
    cats = {p[2] for p in prods}
    assert "원피스" in cats and len(prods) <= 10
    assert demo.keywords()[0] == "디어마미"
