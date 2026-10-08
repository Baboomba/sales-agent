"""용어."""

from __future__ import annotations

from dataclasses import replace

from app.query.model.terms import TERMS, ExampleQuery
from app.query.rules.terms import overlapping_examples


def test_qry_r018_terms_have_no_overlapping_example_questions() -> None:
    """QRY-R018 지금 용어의 예시 질문은 예시 질의의 질문과 겹치지 않는다."""
    assert overlapping_examples(TERMS) == ()


def test_qry_r018_overlap_is_found() -> None:
    """QRY-R018 겹치는 예시 질문을 모두 찾는다.

    위 테스트가 아무것도 못 찾는 구현에서 통과하지 않게 하는 짝이다.
    두 예시 질의가 모두 겹치고, 겹치는 예시 질문은 처음과 끝에, 겹치지 않는 것은 가운데에 둔다.
    예시 질의는 예시 질문과 반대 순서로 둔다 — 결과는 예시 질문의 순서를 따른다.
    """
    terms = replace(
        TERMS,
        example_queries=(
            ExampleQuery("zzz 둘째 질문", "SELECT 2"),
            ExampleQuery("zzz 첫 질문", "SELECT 1"),
        ),
        example_questions=("zzz 첫 질문", "다른 질문", "zzz 둘째 질문"),
    )
    assert overlapping_examples(terms) == ("zzz 첫 질문", "zzz 둘째 질문")
