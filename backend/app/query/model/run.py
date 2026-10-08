"""실행 결과 · 질의 진행 · 질의 단계 (설계서 5.1 · 2.2)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.query.model.failure import ExecutionFailure, GenerationFailure, Stage
from app.query.model.question import Question
from app.query.model.sql import GeneratedSql, Verdict

Row = tuple[object, ...]


@dataclass(frozen=True)
class QueryResult:
    """DB 가 낸 값.

    매출 DB 는 상한+1 행까지 담아 내고, 규칙이 상한으로 자른 뒤에는 상한까지만 담는다.
    """

    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    truncated: bool = False


@dataclass(frozen=True)
class Attempt:
    """시도 하나 — 생성 SQL 또는 생성 실패 하나와, 그 뒤의 판정 · 실행 실패."""

    number: int
    generated: GeneratedSql | None = None
    generation_failure: GenerationFailure | None = None
    verdict: Verdict | None = None
    execution_failure: ExecutionFailure | None = None


@dataclass(frozen=True)
class QueryRun:
    """질문 하나를 처리한 전체. 끝은 실행 결과나 실패 사유이고, 아직이면 둘 다 None."""

    question: Question
    attempts: tuple[Attempt, ...] = field(default_factory=tuple)
    result: QueryResult | None = None
    failure_reason: str | None = None


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
    sql: str  # 행 상한을 붙인 것 — 실행되는 SQL 그대로


@dataclass(frozen=True)
class Completed:
    result: QueryResult


@dataclass(frozen=True)
class Failed:
    reason: str


QueryStep = Generated | Rejected | Validated | Completed | Failed
