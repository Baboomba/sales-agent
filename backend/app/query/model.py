"""질의 도메인의 데이터 형태. 가장 안쪽 계층이라 아무것도 import 하지 않는다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

Stage = Literal["generate", "validate", "execute"]
Outcome = Literal["running", "done", "failed"]
Row = tuple[object, ...]


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    description: str = ""


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[Row, ...]


class QueryState(TypedDict, total=False):
    """그래프가 단계 사이에 넘기는 상태 (docs/design/query.md 2.2)."""

    question: str
    sql: str
    attempt: int
    feedback: str | None
    stage: Stage
    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    truncated: bool
    outcome: Outcome
    reason: str


# --- 이벤트 (docs/design/query.md 2.4) -----------------------------------


@dataclass(frozen=True)
class Generated:
    attempt: int
    sql: str
    type: Literal["generated"] = field(default="generated", init=False)


@dataclass(frozen=True)
class Rejected:
    attempt: int
    stage: Stage
    reason: str
    type: Literal["rejected"] = field(default="rejected", init=False)


@dataclass(frozen=True)
class Validated:
    sql: str
    type: Literal["validated"] = field(default="validated", init=False)


@dataclass(frozen=True)
class Done:
    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    truncated: bool
    type: Literal["done"] = field(default="done", init=False)


@dataclass(frozen=True)
class Failed:
    reason: str
    type: Literal["failed"] = field(default="failed", init=False)


Event = Generated | Rejected | Validated | Done | Failed
