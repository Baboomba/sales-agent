"""실행 결과 · 질의 단계 (설계서 5.1 · 2.2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.query.model.failure import Stage

Row = tuple[object, ...]


@dataclass(frozen=True)
class QueryResult:
    """DB 가 낸 값.

    매출 DB 는 상한+1 행까지 담아 내고, 규칙이 상한으로 자른 뒤에는 상한까지만 담는다.
    """

    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    truncated: bool = False


# --- 질의 단계 (설계서 2.2) ------------------------------------------------


@dataclass(frozen=True)
class Generated:
    attempt: int
    sql: str


@dataclass(frozen=True)
class Rejected:
    """실패해 다시 생성할 때."""

    attempt: int
    stage: Stage
    reason: str


@dataclass(frozen=True)
class Validated:
    sql: str  # 실행되는 SQL 그대로 — 행 상한을 붙였거나, 붙일 것이 없으면 생성 SQL 글 그대로


@dataclass(frozen=True)
class Completed:
    result: QueryResult


@dataclass(frozen=True)
class Failed:
    reason: str


QueryStep = Generated | Rejected | Validated | Completed | Failed
