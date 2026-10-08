"""HTTP 경계. 그래프 이벤트를 SSE 로 옮긴다. 판단은 하지 않는다 — 판단은 rules.py 에 있다."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.query_legacy.catalog import COLUMN_DESCRIPTIONS, EXAMPLE_QUESTIONS, TABLE_DESCRIPTIONS
from app.query_legacy.graph import SqlAgent
from app.query_legacy.model import Event, Table
from app.query_legacy.rules import check_question


class QueryRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def _check(cls, value: str) -> str:
        problem = check_question(value)  # QRY-R001
        if problem:
            raise ValueError(problem)
        return value.strip()


def create_router(agent: SqlAgent, tables: tuple[Table, ...], model: str) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "model": model}

    @router.get("/schema")
    async def schema() -> dict[str, object]:
        """FR-006 표와 열을 업무 설명과 함께 돌려준다."""
        return {
            "tables": [
                {
                    "name": t.name,
                    "description": TABLE_DESCRIPTIONS.get(t.name, t.description),
                    "columns": [
                        {
                            "name": c.name,
                            "type": c.type,
                            "description": COLUMN_DESCRIPTIONS.get((t.name, c.name), ""),
                        }
                        for c in t.columns
                    ],
                }
                for t in tables
            ]
        }

    @router.get("/examples")
    async def examples() -> dict[str, list[str]]:
        """FR-007 예시 질문."""
        return {"questions": list(EXAMPLE_QUESTIONS)}

    @router.post("/queries")
    async def query(request: QueryRequest) -> StreamingResponse:
        """FR-001 · FR-002 · QRY-R012 단계 이벤트를 SSE 로 흘려보낸다."""
        return StreamingResponse(
            _sse(agent.stream(request.question)),
            media_type="text/event-stream",
            # 프록시가 응답을 모았다가 한꺼번에 보내지 않게 한다
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router


async def _sse(events: AsyncIterator[Event]) -> AsyncIterator[str]:
    async for event in events:
        payload = {k: v for k, v in dataclasses.asdict(event).items() if k != "type"}
        yield f"event: {event.type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
