"""회귀: 토큰이 갱신되는 순간 DB 에 되써야 한다 (회전분 유실 → 다음 실행 invalid_grant 사고 방지)."""
import time

from cafe24_ops.clients import cafe24_client as cc
from cafe24_ops.store import Store


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.text = str(payload)

    def json(self):
        return self._p


def test_refresh_writes_back_immediately(tmp_path, monkeypatch):
    store = Store(f"sqlite:///{tmp_path}/t.db")
    store.kv_set(cc.KV_ACCESS, "old-access")
    store.kv_set(cc.KV_REFRESH, "old-refresh")

    calls = []

    def fake_post(url, headers=None, data=None, timeout=None):
        calls.append(data)
        return _Resp(200, {"access_token": "new-access", "refresh_token": "new-refresh",
                           "expires_in": 7200, "scopes": cc.SCOPES})

    monkeypatch.setattr(cc.requests, "post", fake_post)
    client = cc.Cafe24Client("mall", "cid", "sec", "old-access", "old-refresh", store=store, expires_at=1)

    # 만료된 상태에서 GET → 먼저 refresh → DB 저장 → 실제 호출
    def fake_get(url, headers=None, params=None, timeout=None):
        assert headers["Authorization"] == "Bearer new-access"
        return _Resp(200, {"count": 1})

    monkeypatch.setattr(client.session, "get", fake_get)
    assert client.get("/admin/orders/count", {}) == {"count": 1}

    assert calls[0]["grant_type"] == "refresh_token" and calls[0]["refresh_token"] == "old-refresh"
    assert store.kv_get(cc.KV_REFRESH) == "new-refresh"   # 회전분 즉시 영속
    assert store.kv_get(cc.KV_ACCESS) == "new-access"
    assert int(store.kv_get(cc.KV_EXPIRES)) > time.time()
    assert cc.missing_scopes(store.kv_get(cc.KV_SCOPES)) == []


def test_missing_scopes_detects_narrow_reauth():
    assert cc.missing_scopes("mall.read_order,mall.read_customer") == [
        "mall.read_community", "mall.read_product", "mall.read_category",
        "mall.read_application", "mall.read_analytics"]


def test_from_store_prefers_db_over_env(tmp_path, monkeypatch):
    monkeypatch.setattr("cafe24_ops.config._loaded", True)
    monkeypatch.setenv("CAFE24_MALL_ID", "mall")
    monkeypatch.setenv("CAFE24_CLIENT_ID", "cid")
    monkeypatch.setenv("CAFE24_CLIENT_SECRET", "sec")
    monkeypatch.setenv("CAFE24_REFRESH_TOKEN", "env-refresh")
    store = Store(f"sqlite:///{tmp_path}/t.db")
    store.kv_set(cc.KV_REFRESH, "db-refresh")
    c = cc.Cafe24Client.from_store(store)
    assert c.refresh == "db-refresh"
