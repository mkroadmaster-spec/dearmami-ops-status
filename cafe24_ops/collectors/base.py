"""수집기 공통 정의. 채널 하나 = Collector 하나. 자격증명 없으면 자동 스킵."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

Fact = dict[str, Any]


def fact(date: str, source: str, metric: str, value: float, **dims: Any) -> Fact:
    return {"date": date, "source": source, "metric": metric, "value": float(value or 0), "dims": dims}


class PartialFailure(Exception):
    """보조 지표 일부 실패 — 수집 전체를 막지 않고 기록만 한다. facts 는 그대로 upsert."""

    def __init__(self, facts: list[Fact], errors: list[str]):
        super().__init__("; ".join(errors))
        self.facts = facts
        self.errors = errors


@dataclass
class Collector:
    name: str                 # 로그/상태 키 (= facts.source)
    label: str                # 화면 표시명
    step: str                 # 연결 가이드 단계 (docs/CONNECT-GUIDE.md)
    required_env: tuple[str, ...]
    is_configured: Callable[[], bool]
    collect: Callable[[Any, str], list[Fact]]     # (store, date) -> facts
    demo: Callable[[str], list[Fact]]             # (date) -> facts (데모 데이터)
    doc: str = ""             # 발급 안내 문서
    tab: str = "운영현황"       # 대시보드 탭
    optional_env: tuple[str, ...] = field(default_factory=tuple)
    sources: tuple[str, ...] = field(default_factory=tuple)   # 이 수집기가 내는 facts.source 목록 (기본 = name)

    def all_sources(self) -> tuple[str, ...]:
        return self.sources or (self.name,)
