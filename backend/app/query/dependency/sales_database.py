"""매출 DB — 표 목록을 내고, SQL 을 읽기 전용으로 실행한다 (설계서 5.2)."""

from __future__ import annotations

from typing import Protocol

from app.query.model.failure import ExecutionFailure
from app.query.model.question import Table
from app.query.model.run import QueryResult


class SalesDatabase(Protocol):
    def tables(self) -> tuple[Table, ...]:
        """일반 표와 그 열(이름 · 타입)을 DB 의 순서대로. 업무 설명은 비어 있다 (QRY-R017)."""
        ...

    def execute(self, sql: str, fetch: int) -> QueryResult | ExecutionFailure:
        """읽기 전용으로 실행해 많아야 `fetch` 행까지 돌려준다. 실패는 실패 모델로 돌려준다."""
        ...
