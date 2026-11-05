"""CSV 업로드 채널 — 공개 API 가 없는 매체(네이버 GFA·모비온 등)의 리포트 CSV 를 읽어 광고 지표로 넣는다.

폴더: data/manual/<채널키>/*.csv   (채널키: gfa, mobon, 또는 아무 영문 소문자)
헤더(한글/영문 모두 인식): 날짜|date, 광고비|cost|ad_cost, 노출|impressions|imp, 클릭|clicks, 전환|conversions|conv, 전환매출|revenue|ad_revenue
- 날짜 형식: 2026-11-01 / 2026.11.01 / 20261101 / 2026/11/01
- 같은 날짜가 여러 파일·여러 줄에 있으면 합산 (캠페인별 행도 그대로 넣으면 됨)
- 숫자의 쉼표·원 표기 허용 ("1,234,000원")
- 인코딩: UTF-8 또는 CP949(엑셀 저장) 자동 판별
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from .. import config

ROOT_DIR = config.ROOT / "data" / "manual"
LABELS = {"gfa": "네이버 GFA", "mobon": "모비온", "criteo": "크리테오", "brand_search": "네이버 브랜드검색"}
_COLS = {
    "date": ("날짜", "일자", "일", "date", "day", "기준일"),
    "ad_cost": ("광고비", "비용", "총비용", "cost", "ad_cost", "spend", "집행금액", "소진액"),
    "impressions": ("노출", "노출수", "노출 수", "impressions", "imp", "impr"),
    "clicks": ("클릭", "클릭수", "클릭 수", "clicks", "click"),
    "conversions": ("전환", "전환수", "전환 수", "구매", "구매수", "conversions", "conv", "purchases"),
    "ad_revenue": ("전환매출", "전환 매출", "매출", "구매액", "전환금액", "revenue", "ad_revenue", "conversion_value", "sales"),
}


def _num(v: Any) -> float:
    s = re.sub(r"[^\d.\-]", "", str(v or ""))
    try:
        return float(s) if s not in ("", "-", ".") else 0.0
    except ValueError:
        return 0.0


def _date(v: Any) -> str | None:
    m = re.search(r"(\d{4})[.\-/]?(\d{2})[.\-/]?(\d{2})", str(v or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _read(path: Path) -> list[dict[str, str]]:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    return []


def _col(headers: list[str], key: str) -> str | None:
    norm = {h.strip().lower().replace(" ", ""): h for h in headers if h}
    for cand in _COLS[key]:
        c = cand.lower().replace(" ", "")
        if c in norm:
            return norm[c]
    for h_norm, h in norm.items():  # 부분 일치 (예: "광고비(원)")
        if any(c.lower().replace(" ", "") in h_norm for c in _COLS[key]):
            return h
    return None


def channels() -> list[str]:
    if not ROOT_DIR.exists():
        return []
    return sorted(p.name for p in ROOT_DIR.iterdir() if p.is_dir() and list(p.glob("*.csv")))


@lru_cache(maxsize=8)
def load(channel: str) -> dict[str, dict[str, float]]:
    """{date: {ad_cost, impressions, clicks, conversions, ad_revenue}} — 폴더 내 모든 CSV 합산."""
    out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for path in sorted((ROOT_DIR / channel).glob("*.csv")):
        rows = _read(path)
        if not rows:
            continue
        headers = list(rows[0].keys())
        dcol = _col(headers, "date")
        if not dcol:
            continue
        cols = {k: _col(headers, k) for k in ("ad_cost", "impressions", "clicks", "conversions", "ad_revenue")}
        for r in rows:
            d = _date(r.get(dcol))
            if not d:
                continue
            for k, c in cols.items():
                if c:
                    out[d][k] += _num(r.get(c))
    return {d: dict(v) for d, v in out.items()}


def day(channel: str, d: str) -> dict[str, float] | None:
    return load(channel).get(d)


def status() -> list[dict[str, Any]]:
    out = []
    for ch in channels():
        data = load(ch)
        out.append({"channel": ch, "label": LABELS.get(ch, ch), "files": len(list((ROOT_DIR / ch).glob("*.csv"))),
                    "days": len(data), "from": min(data) if data else None, "to": max(data) if data else None})
    return out
