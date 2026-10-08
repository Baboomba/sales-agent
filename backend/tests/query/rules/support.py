"""규칙 테스트가 함께 쓰는 단언."""

from __future__ import annotations


def assert_reason(reason: object) -> str:
    """사유가 글이고 비어 있지 않은지 본다. None · 빈 글 · 공백뿐인 글이면 실패한다.

    사유 문구는 설계서가 정하지 않으므로 글자를 견주지 않는다 (테스트 규칙 3절).
    """
    assert isinstance(reason, str)
    assert reason.strip() != ""
    return reason
