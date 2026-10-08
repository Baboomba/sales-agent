"""HTTP 경계. 입력 검증과 SSE 이벤트 순서를 확인한다."""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.query_legacy.catalog import EXAMPLE_QUESTIONS
from app.query_legacy.ports import GeneratorUnavailable
from tests.fakes import FakeDatabase, ScriptedGenerator, sql_json

SETTINGS = Settings()


def client_for(generator: ScriptedGenerator) -> httpx.AsyncClient:
    app = create_app(SETTINGS, generator=generator, database=FakeDatabase())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.mark.parametrize("question", ["", "   ", "가" * 301])
async def test_qry_r001_invalid_question_is_422(question: str) -> None:
    """QRY-R001 빈 질문 · 공백 · 301자는 그래프를 돌리지 않고 422."""
    generator = ScriptedGenerator([])
    async with client_for(generator) as client:
        response = await client.post("/api/queries", json={"question": question})
    assert response.status_code == 422
    assert generator.calls == 0


async def test_qry_r001_300_chars_is_accepted() -> None:
    """QRY-R001 300자 질문은 받는다."""
    async with client_for(ScriptedGenerator([sql_json("SELECT 1")])) as client:
        response = await client.post("/api/queries", json={"question": "가" * 300})
    assert response.status_code == 200


async def test_qry_r012_success_stream_order() -> None:
    """QRY-R012 SSE 로 generated → validated → done 을 순서대로 보낸다."""
    async with client_for(ScriptedGenerator([sql_json("SELECT region FROM stores")])) as client:
        response = await client.post("/api/queries", json={"question": "지역"})
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["generated", "validated", "done"]
    assert events[2][1]["columns"] == ["n"]


async def test_qry_r012_failure_stream_ends_with_failed() -> None:
    """QRY-R012 실패하면 마지막 이벤트가 failed 하나다."""
    generator = ScriptedGenerator([GeneratorUnavailable("connection refused")])
    async with client_for(generator) as client:
        response = await client.post("/api/queries", json={"question": "지역"})
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["failed"]
    assert events[0][1]["reason"] == "connection refused"


async def test_qry_r017_schema_keeps_database_order_with_catalog_descriptions() -> None:
    """QRY-R017 DB 의 표 · 열 순서 그대로, 카탈로그 설명을 붙이고 없으면 빈 문자열이다."""
    async with client_for(ScriptedGenerator([])) as client:
        response = await client.get("/api/schema")
    tables = response.json()["tables"]
    assert [t["name"] for t in tables] == ["stores", "orders"]
    stores = tables[0]
    assert stores["description"] == "매장"
    assert [c["name"] for c in stores["columns"]] == ["store_id", "name", "region"]
    assert stores["columns"][0]["description"] == ""
    assert stores["columns"][2]["description"].startswith("지역")


async def test_examples_come_from_catalog() -> None:
    """FR-007 카탈로그의 예시 질문을 그대로 돌려준다."""
    async with client_for(ScriptedGenerator([])) as client:
        response = await client.get("/api/examples")
    assert response.json()["questions"] == list(EXAMPLE_QUESTIONS)
