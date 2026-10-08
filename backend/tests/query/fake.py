"""질의 도메인 테스트가 함께 쓰는 가짜 (테스트 규칙 7.1 — 도메인마다 한 자리).

가짜는 정해 둔 답을 차례로 돌려주고, 받은 것을 기록하기만 한다. 판단을 넣지 않는다 (5절).
답 자리에 예외를 두면 그 차례에 그 예외를 던진다.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass

from app.query.model.failure import ExecutionFailure, GenerationFailure
from app.query.model.question import Question, Table
from app.query.model.run import QueryResult
from app.query.model.sql import GeneratedSql, SqlShape
from app.query.model.terms import Terms


class ScriptedModel:
    """언어 모델 대신 쓴다."""

    def __init__(self, replies: Iterable[str | Exception]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@dataclass(frozen=True)
class GenerateCall:
    """생성기가 받은 것 하나."""

    question: Question
    tables: tuple[Table, ...]
    terms: Terms
    last_reason: str | None


class ScriptedGenerator:
    """생성기 대신 쓴다."""

    def __init__(self, replies: Iterable[GeneratedSql | GenerationFailure | Exception]) -> None:
        self._replies = list(replies)
        self.calls: list[GenerateCall] = []

    async def generate(
        self,
        question: Question,
        tables: tuple[Table, ...],
        terms: Terms,
        *,
        last_reason: str | None,
    ) -> GeneratedSql | GenerationFailure:
        self.calls.append(GenerateCall(question, tables, terms, last_reason))
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class ScriptedAnalyzer:
    """SQL 분석기 대신 쓴다. 분석한 글과 행 상한을 붙여 달라고 받은 것을 기록한다."""

    def __init__(self, shapes: Iterable[SqlShape], limited: Iterable[str] = ()) -> None:
        self._shapes = list(shapes)
        self._limited = list(limited)
        self.analyzed: list[str] = []
        self.limit_calls: list[tuple[str, int]] = []

    def analyze(self, sql: str) -> SqlShape:
        self.analyzed.append(sql)
        return self._shapes.pop(0)

    def attach_limit(self, sql: str, limit: int) -> str:
        self.limit_calls.append((sql, limit))
        return self._limited.pop(0)


class ScriptedDatabase:
    """매출 DB 대신 쓴다. 실행한 SQL · 가져올 행 수와 실행한 스레드를 기록한다."""

    def __init__(
        self,
        tables: tuple[Table, ...],
        results: Iterable[QueryResult | ExecutionFailure | Exception],
    ) -> None:
        self._tables = tables
        self._results = list(results)
        self.table_reads = 0
        self.executed: list[tuple[str, int]] = []
        self.threads: list[int] = []

    def tables(self) -> tuple[Table, ...]:
        self.table_reads += 1
        return self._tables

    def execute(self, sql: str, fetch: int) -> QueryResult | ExecutionFailure:
        self.executed.append((sql, fetch))
        self.threads.append(threading.get_ident())
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
