"""용어 (설계서 3절)."""

from __future__ import annotations

from dataclasses import replace

from app.query.model.question import Table
from app.query.model.terms import Terms


def describe_tables(tables: tuple[Table, ...], terms: Terms) -> tuple[Table, ...]:
    """QRY-R017 DB 의 표 · 열에 용어의 업무 설명을 붙인다. 순서는 DB 그대로, 없으면 빈 문자열."""
    return tuple(
        replace(
            table,
            description=terms.table_descriptions.get(table.name, ""),
            columns=tuple(
                replace(
                    column,
                    description=terms.column_descriptions.get((table.name, column.name), ""),
                )
                for column in table.columns
            ),
        )
        for table in tables
    )


def overlapping_examples(terms: Terms) -> tuple[str, ...]:
    """QRY-R018 예시 질문 가운데 예시 질의의 질문과 겹치는 것. 예시 질문의 순서대로 낸다."""
    asked = {example.question for example in terms.example_queries}
    return tuple(question for question in terms.example_questions if question in asked)
