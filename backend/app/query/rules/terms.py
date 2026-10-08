"""용어 (설계서 3절)."""

from __future__ import annotations

from app.query.model.terms import Terms


def overlapping_examples(terms: Terms) -> tuple[str, ...]:
    """QRY-R018 예시 질문 가운데 예시 질의의 질문과 겹치는 것. 예시 질문의 순서대로 낸다."""
    asked = {example.question for example in terms.example_queries}
    return tuple(question for question in terms.example_questions if question in asked)
