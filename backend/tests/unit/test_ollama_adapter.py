"""Ollama 어댑터가 모델 서버 장애를 사용자가 고칠 수 있는 사유로 옮기는지 본다."""

from __future__ import annotations

import httpx
from ollama import ResponseError

from app.query.adapters.ollama import unavailable_reason


def test_qry_r013_connection_failure_reason() -> None:
    """QRY-R013 연결 실패는 서버가 떠 있는지 확인하라고 알린다."""
    reason = unavailable_reason(httpx.ConnectError("refused"), model="m", timeout_seconds=15)
    assert reason.startswith("모델 서버에 연결할 수 없습니다")


def test_qry_r013_timeout_reason_names_the_limit() -> None:
    """QRY-R013 시간 초과는 제한 시간과 함께 알린다."""
    reason = unavailable_reason(httpx.ReadTimeout("slow"), model="m", timeout_seconds=15)
    assert reason.startswith("모델 응답이 15초를 넘었습니다")


def test_qry_r013_error_response_reason_names_the_model() -> None:
    """QRY-R013 오류 응답은 모델 이름과 서버가 준 오류를 알린다."""
    error = ResponseError("model 'm' not found", status_code=404)
    reason = unavailable_reason(error, model="qwen2.5-coder:1.5b", timeout_seconds=15)
    assert reason.startswith("모델 서버가 오류를 돌려줬습니다 (qwen2.5-coder:1.5b)")
    assert "not found" in reason
