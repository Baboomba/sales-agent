"""생성 SQL 과 그것을 업무 말로 나타낸 SQL 구성, 판정 (설계서 5.1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class GeneratedSql:
    """생성기가 낸 SQL. 첫 시도가 1 이다."""

    attempt: int
    text: str


class Qualifier(Enum):
    """표 참조에 붙은 한정자의 종류. 어느 이름이 기본 스키마인지는 SQL 분석기가 안다."""

    NONE = "none"
    DEFAULT_SCHEMA = "default_schema"
    OTHER_SCHEMA = "other_schema"


@dataclass(frozen=True)
class TableRef:
    """SQL 구성 안의 표 참조 하나."""

    name: str
    qualifier: Qualifier = Qualifier.NONE
    is_function: bool = False


@dataclass(frozen=True)
class SqlShape:
    """생성 SQL 이 무엇을 하는지. SQL 분석기가 만든다.

    분석 오류가 있으면 나머지 필드는 의미가 없다.
    """

    parse_error: str | None
    statement_count: int
    is_query: bool
    forbidden: tuple[str, ...]  # 문장 안에 든 쓰기 · 정의 · 관리 구문 이름
    tables: tuple[TableRef, ...]
    cte_names: tuple[str, ...]
    outer_limit: int | None  # 바깥 행 상한. 없거나 수가 아니면 None, 음수는 그대로 싣는다


@dataclass(frozen=True)
class Accepted:
    """판정 — 통과. limit 이 있으면 그 행 상한을 붙이고, None 이면 SQL 을 그대로 둔다."""

    limit: int | None


@dataclass(frozen=True)
class Refused:
    """판정 — 거부."""

    reason: str


Verdict = Accepted | Refused
