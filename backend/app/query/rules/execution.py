"""실행 실패의 사유 (설계서 3절)."""

from __future__ import annotations

from app.query.model.failure import ExecutionFailure, ExecutionFailureKind, QueryLimits


def execution_failure_reason(failure: ExecutionFailure, limits: QueryLimits) -> str:
    """QRY-R015 · QRY-R009 실행 실패를 다음 생성에 넘길 사유로 옮긴다.

    별칭의 표 없음이면 그 별칭의 표를 JOIN 했는지와 열 이름을 확인하라는 안내를 붙인다 (QRY-R015).
    SQLite 는 표가 없을 때와 열 이름만 틀렸을 때를 같은 오류로 낸다 (#47). 오류 글만으로는
    작은 모델이 고칠 곳을 찾지 못한다 (설계서 3절 근거). 시간 초과면 제한 시간과 더 가벼운
    질의로 바꾸라는 안내를 준다 (QRY-R009).
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
                f"{failure.detail} — 별칭 '{alias}' 의 표가 FROM 이나 JOIN 에 있는지, "
                f"있다면 그 표에 이 열이 있는지 확인하라. 표가 없으면 그 표를 JOIN 하고, "
                "열이 없으면 표 목록의 열 이름을 써라."
            )
        case ExecutionFailureKind.REFUSED:
            return failure.detail
