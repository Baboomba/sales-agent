"""질의 도메인이 밖에서 받는 것의 인터페이스. 구현은 adapters/ 에 있다."""

from __future__ import annotations

from typing import Protocol

from app.query.model import QueryResult, Table


class GeneratorUnavailable(Exception):
    """모델 서버에 닿지 않는다. 다시 만들어도 나아지지 않는 실패다 (QRY-R013)."""


class ExecutionError(Exception):
    """DB 가 SQL 실행을 거부했거나 제한 시간을 넘겼다. 다시 만들면 나을 수 있다 (QRY-R006)."""


class SqlGenerator(Protocol):
    async def generate(self, prompt: str) -> str:
        """모델의 날 출력을 돌려준다. 해석은 rules.parse_generation 이 한다."""
        ...


class SalesDatabase(Protocol):
    def schema(self) -> tuple[Table, ...]: ...

    def execute(self, sql: str) -> QueryResult:
        """읽기 전용으로 실행한다. 실패하면 ExecutionError."""
        ...
