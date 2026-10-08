"""보조 조회 — 표 · 열과 예시 질문 (설계서 2.4)."""

from __future__ import annotations

from app.query.dependency.sales_database import SalesDatabase
from app.query.model.question import Table
from app.query.model.terms import Terms
from app.query.rules.terms import describe_tables


class Lookup:
    def __init__(self, database: SalesDatabase, terms: Terms) -> None:
        # 설계서 2.4 표 목록은 만들 때 한 번 읽는다. 매출 DB 는 읽기 전용이라 바뀌지 않는다.
        self._tables = describe_tables(database.tables(), terms)
        self._example_questions = terms.example_questions

    def tables(self) -> tuple[Table, ...]:
        """QRY-R017 DB 의 표 · 열을 DB 의 순서대로, 용어의 업무 설명을 붙여 돌려준다."""
        return self._tables

    def example_questions(self) -> tuple[str, ...]:
        """용어의 예시 질문을 그 순서대로 돌려준다. 겹치지 않는 것은 QRY-R018 규칙 테스트가 본다."""
        return self._example_questions
