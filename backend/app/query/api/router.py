"""질의 도메인의 HTTP 경로 (설계서 2.2 · 2.3 · 2.4).

유스케이스만 부른다. 규칙 · 의존성을 직접 부르지 않는다 (코드 아키텍처 2.5).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.query.api.dto import (
    ExamplesResponse,
    HealthResponse,
    QueryRequest,
    SchemaResponse,
    examples_response,
    health_response,
    schema_response,
    step_event,
)
from app.query.model.question import Question
from app.query.model.run import QueryStep
from app.query.usecase.lookup import Lookup
from app.query.usecase.query_flow import QueryFlow

# 설계서 2.2 프록시가 이벤트를 모았다가 한꺼번에 보내지 않게 한다.
_NO_BUFFERING = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def create_router(flow: QueryFlow, lookup: Lookup, model_name: str) -> APIRouter:
    router = APIRouter(prefix="/api")

    # 경로 함수는 모듈 수준 함수를 부르기만 한다 — 안쪽 함수는 변이 테스트가 바꾸지 않는다.
    @router.post("/queries")
    async def query(request: QueryRequest) -> StreamingResponse:
        return _start_query(flow, request)

    @router.get("/schema")
    async def schema() -> SchemaResponse:
        return schema_response(lookup.tables())

    @router.get("/examples")
    async def examples() -> ExamplesResponse:
        return examples_response(lookup.example_questions())

    @router.get("/health")
    async def health() -> HealthResponse:
        return health_response(model_name)

    return router


def _start_query(flow: QueryFlow, request: QueryRequest) -> StreamingResponse:
    """QRY-R012 질의 단계를 SSE 이벤트로 흘려보낸다. 맞지 않는 질문은 422 (QRY-R001)."""
    started = flow.start(Question(request.question))
    if isinstance(started, str):
        raise HTTPException(status_code=422, detail=started)
    return StreamingResponse(_sse(started), media_type="text/event-stream", headers=_NO_BUFFERING)


async def _sse(steps: AsyncIterator[QueryStep]) -> AsyncIterator[str]:
    """이벤트 하나는 `event:` 줄과 `data:` 줄 둘이고 빈 줄로 끝난다 (설계서 2.2)."""
    async for step in steps:
        name, data = step_event(step)
        yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
