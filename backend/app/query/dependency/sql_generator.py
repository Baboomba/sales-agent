"""생성기 — 질문에 답하는 SQL 을 만든다 (설계서 5.2)."""

from __future__ import annotations

from typing import Protocol

from app.query.model.failure import GenerationFailure
from app.query.model.question import Question, Table
from app.query.model.sql import GeneratedSql
from app.query.model.terms import Terms


class SqlGenerator(Protocol):
    async def generate(
        self,
        question: Question,
        tables: tuple[Table, ...],
        terms: Terms,
        *,
        attempt: int,
        last_reason: str | None,
    ) -> GeneratedSql | GenerationFailure:
        """표 목록은 규칙이 업무 설명을 붙인 것이다(QRY-R017). 실패는 실패 모델로 돌려준다."""
        ...
