"""질문 규칙 (설계서 3절)."""

from __future__ import annotations

from app.query.model.question import Question

_QUESTION_MAX_LENGTH = 300


def check_question(question: Question) -> str | None:
    """QRY-R001 질문이 받을 수 있는 모양인지 본다. 문제가 있으면 사유, 없으면 None."""
    length = len(question.text.strip())
    if length == 0:
        return "질문이 비어 있습니다."
    if length > _QUESTION_MAX_LENGTH:
        return f"질문은 {_QUESTION_MAX_LENGTH}자 이하여야 합니다."
    return None
