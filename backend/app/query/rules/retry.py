"""실패 뒤에 무엇을 할지 (설계서 3절)."""

from __future__ import annotations

from app.query.model.failure import GenerationFailure, GenerationFailureKind, QueryLimits, Stage
from app.query.model.run import Failed, Rejected


def after_rejection(
    attempt: int, stage: Stage, reason: str, limits: QueryLimits
) -> Rejected | Failed:
    """QRY-R006 · QRY-R007 한도 안이면 사유를 붙여 다시 생성하고, 한도에 닿으면 실패로 끝낸다."""
    if attempt >= limits.max_attempts:
        return Failed(
            f"{attempt}번 시도했지만 실행할 수 있는 SQL 을 만들지 못했습니다. 마지막 사유: {reason}"
        )
    return Rejected(attempt=attempt, stage=stage, reason=reason)


def after_generation_failure(
    attempt: int, failure: GenerationFailure, limits: QueryLimits
) -> Rejected | Failed:
    """QRY-R013 · QRY-R010 생성 실패 뒤에 무엇을 할지 정한다.

    모델 서버 장애면 다시 생성하지 않고 장애 종류를 알 수 있는 사유로 끝낸다 (QRY-R013).
    출력 형식 실패는 장애가 아니다 — 생성기가 지은 세부를 사유로 다시 생성한다 (QRY-R010).
    """
    match failure.kind:
        case GenerationFailureKind.FORMAT:
            return after_rejection(attempt, Stage.GENERATE, failure.detail, limits)
        case GenerationFailureKind.TIMEOUT:
            return Failed(
                f"모델 응답이 {limits.generation_timeout_seconds:g}초를 넘었습니다. "
                "더 작은 모델을 쓰거나, Mac 이면 Docker 대신 호스트의 Ollama 를 쓰세요."
            )
        case GenerationFailureKind.ERROR_RESPONSE:
            return Failed(
                f"모델 서버가 오류를 돌려줬습니다: {failure.detail}. "
                "모델을 받았는지 확인하세요 (ollama pull)."
            )
        case GenerationFailureKind.CONNECTION:
            return Failed(
                "모델 서버에 연결할 수 없습니다. Ollama 가 떠 있는지 확인하세요. "
                f"({failure.detail})"
            )
