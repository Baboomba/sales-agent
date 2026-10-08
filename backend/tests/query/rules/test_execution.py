"""실행 실패의 사유."""

from __future__ import annotations

from app.query.model.failure import ExecutionFailure, ExecutionFailureKind, QueryLimits
from app.query.rules.execution import execution_failure_reason

LIMITS = QueryLimits(
    max_attempts=3, row_limit=200, generation_timeout_seconds=15, query_timeout_seconds=7
)
DETAIL = "no such column: zq.ordered_on"


def test_qry_r015_missing_alias_adds_guidance_naming_the_alias() -> None:
    """QRY-R015 별칭의 표 없음이면 세부를 남기고, 그 별칭을 짚는 안내를 덧붙인다.

    별칭은 실패 모델의 별칭에서 온다. 세부에 별칭 꼴이 없어도 안내가 붙어야 한다 —
    규칙은 바깥의 오류 글을 해석하지 않는다.
    """
    detail = "zzz unknown reference"
    failure = ExecutionFailure(ExecutionFailureKind.MISSING_ALIAS, detail, alias="zq")
    reason = execution_failure_reason(failure, LIMITS)
    assert detail in reason
    assert "zq" in reason
    assert "JOIN" in reason.upper()  # 설계서 4절이 정한 「JOIN 안내」. 대소문자는 묻지 않는다


def test_qry_r015_other_failure_is_passed_on_as_it_is() -> None:
    """QRY-R015 다른 실행 실패는 그대로다 — 안내를 붙이지 않는다."""
    failure = ExecutionFailure(ExecutionFailureKind.REFUSED, DETAIL)
    assert execution_failure_reason(failure, LIMITS) == DETAIL


def test_qry_r009_timeout_reason_names_the_timeout_and_asks_for_a_lighter_query() -> None:
    """QRY-R009 시간 초과의 사유에는 실행 제한 시간과 더 가벼운 질의로 바꾸라는 안내가 있다.

    「가벼운」은 설계서가 정한 안내의 낱말이고, 넣은 세부(`interrupted`)에는 없다.
    """
    failure = ExecutionFailure(ExecutionFailureKind.TIMEOUT, "interrupted")
    reason = execution_failure_reason(failure, LIMITS)
    assert "7" in reason
    assert "가벼운" in reason
