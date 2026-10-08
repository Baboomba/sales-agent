"""질문 규칙."""

from __future__ import annotations

import pytest

from app.query.model.question import Question
from app.query.rules.question import check_question
from tests.query.support import assert_reason


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_qry_r001_blank_question_is_refused(text: str) -> None:
    """QRY-R001 비었거나 공백뿐인 질문은 받지 않는다."""
    assert_reason(check_question(Question(text)))


@pytest.mark.parametrize("text", ["가", "가" * 300], ids=["1자", "300자"])
def test_qry_r001_question_of_1_to_300_chars_is_accepted(text: str) -> None:
    """QRY-R001 1자와 300자는 받는다."""
    assert check_question(Question(text)) is None


def test_qry_r001_question_of_301_chars_is_refused() -> None:
    """QRY-R001 301자는 받지 않는다."""
    assert_reason(check_question(Question("가" * 301)))


def test_qry_r001_surrounding_spaces_do_not_count_toward_length() -> None:
    """QRY-R001 앞뒤 공백은 길이에 들지 않는다 — 300자 앞뒤에 공백을 붙여도 받는다."""
    assert check_question(Question("  " + "가" * 300 + "  ")) is None


def test_qry_r001_inner_spaces_count_toward_length() -> None:
    """QRY-R001 안쪽 공백은 길이에 든다.

    앞뒤 공백을 빼면 301자(거부), 모든 공백을 빼면 151자(통과)가 되는 질문으로 두 해석을 가른다.
    """
    assert_reason(check_question(Question("가 " * 151)))
