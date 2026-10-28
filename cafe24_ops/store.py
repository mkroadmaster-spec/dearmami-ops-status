"""저장소: 기본 SQLite(data/ops.db), DATABASE_URL 이 postgres면 Postgres.

테이블
- facts(date, source, metric, dims(json), value)  : 수집 원천(정규화)
- kpi_daily(date, metric, value)                   : 일자별 집계
- app_kv(key, value, updated_at)                   : 토큰 등 영속 값 (Secret 보다 우선)
- collect_log(run_at, date, source, status, message)
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import config

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS facts (
        date TEXT NOT NULL, source TEXT NOT NULL, metric TEXT NOT NULL,
        dims TEXT NOT NULL DEFAULT '{}', value REAL NOT NULL DEFAULT 0,
        PRIMARY KEY (date, source, metric, dims))""",
    """CREATE TABLE IF NOT EXISTS kpi_daily (
        date TEXT NOT NULL, metric TEXT NOT NULL, value REAL,
        PRIMARY KEY (date, metric))""",
    """CREATE TABLE IF NOT EXISTS app_kv (
        key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS collect_log (
        run_at TEXT, date TEXT, source TEXT, status TEXT, message TEXT)""",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, url: str | None = None):
        self.url = url if url is not None else config.database_url()
        self.is_pg = self.url.startswith(("postgres://", "postgresql://"))
        if self.is_pg:
            import psycopg  # type: ignore

            self.conn = psycopg.connect(self.url, autocommit=True)
        else:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            path = self.url.replace("sqlite:///", "") if self.url else str(config.DATA_DIR / "ops.db")
            # FastAPI 는 요청을 스레드풀에서 처리 → 스레드 공유 허용 + 락으로 직렬화
            self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        for ddl in SCHEMA:
            self.exec(ddl)

    # ---- low level -------------------------------------------------------
    def _q(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.is_pg else sql

    def exec(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(self._q(sql), tuple(params))
            cur.close()

    def rows(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(self._q(sql), tuple(params))
            cols = [d[0] for d in cur.description]
            out = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
        return out

    def _upsert(self, table: str, cols: list[str], keys: list[str], values: list[tuple]) -> None:
        if not values:
            return
        ph = ",".join("?" * len(cols))
        upd = ",".join(f"{c}=excluded.{c}" for c in cols if c not in keys)
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph}) ON CONFLICT ({','.join(keys)}) DO UPDATE SET {upd}"
        with self._lock:
            cur = self.conn.cursor()
            cur.executemany(self._q(sql), values)
            cur.close()

    # ---- facts -----------------------------------------------------------
    def upsert_facts(self, facts: Iterable[dict[str, Any]]) -> int:
        vals = []
        for f in facts:
            dims = json.dumps(f.get("dims") or {}, sort_keys=True, ensure_ascii=False)
            vals.append((f["date"], f["source"], f["metric"], dims, float(f.get("value") or 0)))
        self._upsert("facts", ["date", "source", "metric", "dims", "value"],
                     ["date", "source", "metric", "dims"], vals)
        return len(vals)

    def delete_facts(self, date: str, source: str) -> None:
        """재수집 전 삭제(차원 바뀐 낡은 행 제거). 부분 실패 소스는 호출하지 말 것."""
        self.exec("DELETE FROM facts WHERE date=? AND source=?", (date, source))

    def facts(self, date_from: str, date_to: str, source: str | None = None,
              metric: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT date, source, metric, dims, value FROM facts WHERE date BETWEEN ? AND ?"
        params: list[Any] = [date_from, date_to]
        if source:
            sql += " AND source=?"
            params.append(source)
        if metric:
            sql += " AND metric=?"
            params.append(metric)
        out = self.rows(sql + " ORDER BY date", params)
        for r in out:
            r["dims"] = json.loads(r["dims"] or "{}")
        return out

    def clear_all_facts(self) -> None:
        self.exec("DELETE FROM facts")
        self.exec("DELETE FROM kpi_daily")

    # ---- kpi -------------------------------------------------------------
    def upsert_kpi(self, date: str, kpis: dict[str, float | None]) -> None:
        vals = [(date, k, None if v is None else float(v)) for k, v in kpis.items()]
        self._upsert("kpi_daily", ["date", "metric", "value"], ["date", "metric"], vals)

    def kpi_range(self, date_from: str, date_to: str) -> dict[str, dict[str, float | None]]:
        rows = self.rows("SELECT date, metric, value FROM kpi_daily WHERE date BETWEEN ? AND ? ORDER BY date",
                         (date_from, date_to))
        out: dict[str, dict[str, float | None]] = {}
        for r in rows:
            out.setdefault(r["date"], {})[r["metric"]] = r["value"]
        return out

    def date_bounds(self) -> tuple[str | None, str | None]:
        r = self.rows("SELECT MIN(date) AS mn, MAX(date) AS mx FROM kpi_daily")
        return (r[0]["mn"], r[0]["mx"]) if r else (None, None)

    # ---- kv (토큰 영속) -----------------------------------------------------
    def kv_get(self, key: str, default: str = "") -> str:
        r = self.rows("SELECT value FROM app_kv WHERE key=?", (key,))
        return (r[0]["value"] if r and r[0]["value"] is not None else default)

    def kv_set(self, key: str, value: str) -> None:
        self._upsert("app_kv", ["key", "value", "updated_at"], ["key"], [(key, value, _now())])

    def kv_delete(self, *keys: str) -> None:
        for k in keys:
            self.exec("DELETE FROM app_kv WHERE key=?", (k,))

    # ---- log -------------------------------------------------------------
    def log(self, date: str, source: str, status: str, message: str = "") -> None:
        self.exec("INSERT INTO collect_log (run_at, date, source, status, message) VALUES (?,?,?,?,?)",
                  (_now(), date, source, status, message[:2000]))

    def recent_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.rows("SELECT run_at, date, source, status, message FROM collect_log ORDER BY run_at DESC LIMIT ?",
                         (limit,))

    def last_status_by_source(self) -> dict[str, dict[str, Any]]:
        rows = self.rows("SELECT run_at, date, source, status, message FROM collect_log ORDER BY run_at DESC LIMIT 500")
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            out.setdefault(r["source"], r)
        return out
