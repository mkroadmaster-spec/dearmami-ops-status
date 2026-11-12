"""수집 파이프라인 — 날짜별로 등록된 수집기 실행 → facts → kpi_daily.

- live: 자격증명 있는 채널만 수집, 없는 채널은 skip 로그
- demo: 데모 데이터 생성 (틀 확인용)
- 재수집: 성공 소스는 delete_facts 후 upsert (낡은 행 제거), 부분 실패 소스는 upsert 만(기존 정상 데이터 보존)
"""
from __future__ import annotations

from datetime import date as _date, datetime, timedelta, timezone
from typing import Any

from . import config
from .collectors import REGISTRY
from .collectors.base import PartialFailure
from .etl.aggregate import aggregate_day

KST = timezone(timedelta(hours=9))


def yesterday() -> str:
    """반드시 KST 기준 (러너는 UTC — 07:00 KST = 전날 22:00 UTC)."""
    return (datetime.now(KST).date() - timedelta(days=1)).isoformat()


def run_day(store, d: str, mode: str | None = None, skip: set[str] | None = None) -> dict[str, Any]:
    mode = mode or config.mode()
    skip = skip or set()
    result: dict[str, Any] = {"date": d, "mode": mode, "sources": {}}
    for c in REGISTRY:
        if c.name in skip:
            result["sources"][c.name] = {"status": "skip", "message": "--skip"}
            continue
        try:
            if mode == "demo":
                facts = c.demo(d)
                status, msg = "ok", f"demo {len(facts)}건"
            else:
                if not c.is_configured():
                    result["sources"][c.name] = {"status": "skip", "message": "자격증명 없음"}
                    store.log(d, c.name, "skip", "자격증명 없음")
                    continue
                facts = c.collect(store, d)
                status, msg = "ok", f"{len(facts)}건"
            # ADS_ONLY(일부 광고 채널만 재수집) 일 때 ads 는 지우지 않고 덮어쓰기만 → 다른 채널 데이터 보존
            if not (c.name == "ads" and config.env("ADS_ONLY")):
                for src in c.all_sources():
                    store.delete_facts(d, src)
            store.upsert_facts(facts)
        except PartialFailure as pf:
            store.upsert_facts(pf.facts)  # delete 없이 upsert 만
            status, msg = "partial", f"{len(pf.facts)}건, 실패: {pf}"
        except Exception as e:  # noqa: BLE001
            status, msg = "fail", f"{type(e).__name__}: {e}"
        store.log(d, c.name, status, msg)
        result["sources"][c.name] = {"status": status, "message": msg}
    result["kpi"] = aggregate_day(store, d)
    store.kv_set("data_mode", mode)
    store.kv_set("last_run_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return result


def run_range(store, date_to: str, days: int, mode: str | None = None, skip: set[str] | None = None) -> list[dict[str, Any]]:
    end = _date.fromisoformat(date_to)
    out = []
    import sys, time as _t
    t0 = _t.time()
    for n, i in enumerate(range(days - 1, -1, -1), 1):
        out.append(run_day(store, (end - timedelta(days=i)).isoformat(), mode, skip))
        if days > 40 and (n % 30 == 0 or n == days):  # 장기 백필 진행률 (Actions 로그에서 확인)
            el = _t.time() - t0
            print(f"[progress] {n}/{days}일 ({out[-1]['date']}) · 경과 {el/60:.0f}분 · 예상 잔여 {el/n*(days-n)/60:.0f}분", flush=True)
    return out
