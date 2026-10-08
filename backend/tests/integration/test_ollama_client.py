"""Ollama 연결의 연결 제한 시간. 언어 모델은 부르지 않는다 (NFR-005).

연결이 맺어지지 않는 주소로 닿아, 실제 클라이언트가 연결 시간 초과를 내는지 본다.
"""

from __future__ import annotations

import asyncio

import pytest

from app.query.dependency.impl.ollama_client import ollama_complete
from app.query.dependency.impl.ollama_generator import OllamaSqlGenerator
from app.query.model.failure import GenerationFailure, GenerationFailureKind
from app.query.model.question import Question
from app.query.model.terms import TERMS
from tests.query.support import assert_reason

pytestmark = pytest.mark.integration

# 라우팅되지 않는 사설 주소 — 연결 요청이 응답 없이 멈춘다.
UNROUTABLE = "http://10.255.255.1:11434"


async def test_qry_r013_connection_that_hangs_ends_as_connection_failure() -> None:
    """QRY-R013 연결하다 시간이 넘은 것은 연결 실패다 (#48).

    연결 제한 시간은 생성 제한 시간(2초)의 절반이다. 연결에 제한 시간이 없으면 생성 제한 시간에
    끊겨 응답 시간 초과가 되고, 사용자는 「더 작은 모델을 쓰라」는 틀린 안내를 받는다.
    네트워크가 이 주소를 바로 거부하는 곳에서도 연결 실패라 결과는 같다.
    """
    generator = OllamaSqlGenerator(
        ollama_complete(base_url=UNROUTABLE, model="zzz-model", generation_timeout_seconds=2),
        timeout_seconds=2,
    )
    result = await asyncio.wait_for(
        generator.generate(Question("zzz 질문"), (), TERMS, last_reason=None), timeout=5
    )
    assert isinstance(result, GenerationFailure)
    assert result.kind is GenerationFailureKind.CONNECTION
    assert_reason(result.detail)
