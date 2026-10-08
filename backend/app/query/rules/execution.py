"""실행 실패의 사유 (설계서 3절)."""

from __future__ import annotations

from app.query.model.failure import ExecutionFailure, ExecutionFailureKind, QueryLimits


def execution_failure_reason(failure: ExecutionFailure, limits: QueryLimits) -> str:
    """QRY-R015 실행 실패를 다음 생성에 넘길 사유로 옮긴다.

    별칭의 표 없음이면 그 별칭의 표를 JOIN 하라는 안내를 붙인다. 오류 글만으로는 작은 모델이
    고칠 곳을 찾지 못한다 (설계서 3절 근거).
    """
    match failure.kind:
        case ExecutionFailureKind.TIMEOUT:
            return (
                f"실행 시간이 {limits.query_timeout_seconds:g}초를 넘어 중단했습니다. "
                "더 가벼운 질의로 바꾸세요."
            )
        case ExecutionFailureKind.MISSING_ALIAS:
            alias = failure.alias
            return (
                f"{failure.detail} — 별칭 '{alias}' 의 표가 FROM 이나 JOIN 에 없다. "
                f"'{alias}' 를 쓰려면 그 표를 JOIN 하라."
            )
        case ExecutionFailureKind.REFUSED:
            return failure.detail
