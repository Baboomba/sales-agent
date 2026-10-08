"""질의 한도 (설계서 3절)."""

from __future__ import annotations

from app.query.model.failure import QueryLimits

_MAX_SECONDS_PER_QUESTION = 60  # NFR-003


def check_limits(limits: QueryLimits) -> str | None:
    """QRY-R016 질문 하나의 최악 시간이 1분을 넘는 한도면 사유, 아니면 None."""
    generation = limits.generation_timeout_seconds
    query = limits.query_timeout_seconds
    worst = limits.max_attempts * (generation + query)
    if worst <= _MAX_SECONDS_PER_QUESTION:
        return None
    return (
        f"질문 하나가 최악 {worst:g}초 걸리는 설정입니다 "
        f"(생성 {limits.max_attempts}회 × (생성 {generation:g}초 + 실행 {query:g}초)). "
        f"{_MAX_SECONDS_PER_QUESTION}초 이하가 되게 줄이세요."
    )
