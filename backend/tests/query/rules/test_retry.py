"""실패 뒤에 무엇을 할지."""

from __future__ import annotations

import pytest

from app.query.model.failure import GenerationFailure, GenerationFailureKind, QueryLimits, Stage
from app.query.model.run import Failed, Rejected
from app.query.rules.retry import (
    after_generation_failure,
    after_rejection,
    after_unexpected_error,
)
from tests.query.support import assert_reason

LIMITS = QueryLimits(
    max_attempts=3, row_limit=200, generation_timeout_seconds=13, query_timeout_seconds=5
)
REASON = "허용되지 않은 표입니다: zzz_receipts"
FORMAT = GenerationFailureKind.FORMAT
FORMAT_DETAIL = "zzz 출력이 JSON 이 아닙니다"
CONNECTION = GenerationFailureKind.CONNECTION
ERROR_RESPONSE = GenerationFailureKind.ERROR_RESPONSE
TIMEOUT = GenerationFailureKind.TIMEOUT


# --- QRY-R006 · QRY-R007 재생성과 한도 ------------------------------------


def test_qry_r006_failure_one_before_the_limit_regenerates_with_the_reason() -> None:
    """QRY-R006 한도 바로 앞의 실패도 사유를 그대로 붙여 다시 생성한다."""
    assert after_rejection(2, Stage.VALIDATE, REASON, LIMITS) == Rejected(
        attempt=2, stage=Stage.VALIDATE, reason=REASON
    )


@pytest.mark.parametrize("stage", list(Stage))
def test_qry_r006_every_stage_is_regenerated(stage: Stage) -> None:
    """QRY-R006 생성 · 판정 · 실행 어느 단계의 실패든 다시 생성한다."""
    assert after_rejection(1, stage, REASON, LIMITS) == Rejected(
        attempt=1, stage=stage, reason=REASON
    )


def test_qry_r007_failure_at_the_limit_fails_with_the_last_reason() -> None:
    """QRY-R007 마지막 시도의 실패면 실패로 끝내고 마지막 사유를 알린다."""
    step = after_rejection(3, Stage.EXECUTE, REASON, LIMITS)
    assert isinstance(step, Failed)
    assert REASON in step.reason


def test_qry_r007_single_attempt_limit_fails_on_the_first_failure() -> None:
    """QRY-R007 생성 최대 횟수가 1 이면 첫 실패에서 끝난다."""
    limits = QueryLimits(
        max_attempts=1, row_limit=200, generation_timeout_seconds=13, query_timeout_seconds=5
    )
    step = after_rejection(1, Stage.VALIDATE, REASON, limits)
    assert isinstance(step, Failed)
    assert REASON in step.reason


# --- QRY-R013 모델 서버 장애 ----------------------------------------------


def test_qry_r013_each_outage_kind_has_its_own_reason() -> None:
    """QRY-R013 세부가 같아도 장애 종류마다 사유가 다르다 — 무엇을 고칠지 알 수 있게."""
    connection = after_generation_failure(1, GenerationFailure(CONNECTION, "zzz"), LIMITS)
    error_response = after_generation_failure(1, GenerationFailure(ERROR_RESPONSE, "zzz"), LIMITS)
    timeout = after_generation_failure(1, GenerationFailure(TIMEOUT, "zzz"), LIMITS)
    assert connection != error_response
    assert error_response != timeout
    assert connection != timeout


@pytest.mark.parametrize(
    ("kind", "detail"),
    [
        (GenerationFailureKind.CONNECTION, "zzz connection refused"),
        (GenerationFailureKind.ERROR_RESPONSE, "model 'zzz-model' not found"),
    ],
)
def test_qry_r013_outage_reason_keeps_the_detail(kind: GenerationFailureKind, detail: str) -> None:
    """QRY-R013 연결 실패 · 오류 응답은 한도가 남아도 첫 시도에서 끝난다.

    사유에는 바깥이 준 세부가 남는다.
    """
    step = after_generation_failure(1, GenerationFailure(kind, detail), LIMITS)
    assert isinstance(step, Failed)
    assert detail in step.reason


def test_qry_r013_timeout_reason_names_the_generation_timeout() -> None:
    """QRY-R013 시간 초과는 한도가 남아도 첫 시도에서 끝나고, 사유에 생성 제한 시간이 있다."""
    step = after_generation_failure(
        1, GenerationFailure(GenerationFailureKind.TIMEOUT, "zzz"), LIMITS
    )
    assert isinstance(step, Failed)
    assert "13" in step.reason


@pytest.mark.parametrize("attempt", [1, 2])
def test_qry_r010_format_failure_is_not_an_outage_and_regenerates(attempt: int) -> None:
    """QRY-R010 출력 형식 실패는 장애가 아니다. 한도 안이면 세부를 사유로 붙여 다시 생성한다."""
    step = after_generation_failure(attempt, GenerationFailure(FORMAT, FORMAT_DETAIL), LIMITS)
    assert isinstance(step, Rejected)
    assert (step.attempt, step.stage) == (attempt, Stage.GENERATE)
    assert FORMAT_DETAIL in step.reason


def test_format_failure_at_the_limit_fails_with_its_detail() -> None:
    step = after_generation_failure(3, GenerationFailure(FORMAT, FORMAT_DETAIL), LIMITS)
    assert isinstance(step, Failed)
    assert FORMAT_DETAIL in step.reason


def test_format_failure_with_single_attempt_limit_fails_on_the_first_attempt() -> None:
    limits = QueryLimits(
        max_attempts=1, row_limit=200, generation_timeout_seconds=13, query_timeout_seconds=5
    )
    step = after_generation_failure(1, GenerationFailure(FORMAT, FORMAT_DETAIL), limits)
    assert isinstance(step, Failed)
    assert FORMAT_DETAIL in step.reason


# --- QRY-R012 예상하지 못한 오류 ------------------------------------------


def test_qry_r012_unexpected_error_ends_as_a_failure_with_a_reason() -> None:
    """QRY-R012 예상하지 못한 오류도 실패로 끝내고, 사용자에게 보일 사유가 있다."""
    step = after_unexpected_error()
    assert isinstance(step, Failed)
    assert_reason(step.reason)
