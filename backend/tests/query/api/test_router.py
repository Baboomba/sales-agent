"""HTTP 경계. 유스케이스가 낸 모델을 응답 · SSE 로 옮기는지, 맞지 않는 질문을 422 로 옮기는지 본다.

가짜 의존성으로 조립한 유스케이스를 경로에 끼운다 (테스트 규칙 7.1). 흐름 · 판정은 다른 층이 본다.
SSE 본문은 `read_sse` 로 줄 꼴을 엄격히 보고 JSON 을 풀어 견준다 (설계서 2.2).
"""

from __future__ import annotations

from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from app.query.api.router import create_router
from app.query.model.failure import (
    ExecutionFailure,
    ExecutionFailureKind,
    GenerationFailure,
    GenerationFailureKind,
    QueryLimits,
)
from app.query.model.question import Column, Question, Table
from app.query.model.run import QueryResult
from app.query.model.sql import GeneratedSql, SqlShape, TableRef
from app.query.model.terms import TERMS
from app.query.usecase.lookup import Lookup
from app.query.usecase.query_flow import QueryFlow
from tests.query.fake import ScriptedAnalyzer, ScriptedDatabase, ScriptedGenerator
from tests.query.support import assert_reason, read_sse

LIMITS = QueryLimits(
    max_attempts=3, row_limit=7, generation_timeout_seconds=13, query_timeout_seconds=4
)
DB_TABLES = (
    Table("zzz_sales", (Column("zzz_c", "REAL"), Column("zzz_a", "INTEGER"))),
    Table("zzz_alpha", (Column("zzz_d", "TEXT"),)),
)
TERMS_FOR_TEST = replace(
    TERMS,
    table_descriptions={"zzz_sales": "zzz 매출 표"},
    column_descriptions={("zzz_sales", "zzz_a"): "zzz 끝 열"},
    example_questions=("zzz 둘째 질문", "zzz 첫 질문"),
)
# 판정을 통과하고 붙일 행 상한이 없는 SQL 구성.
PASSING = SqlShape(
    parse_error=None,
    statement_count=1,
    is_query=True,
    forbidden=(),
    tables=(TableRef("zzz_sales"),),
    cte_names=(),
    outer_limit=3,
)


def client_for(
    generator: ScriptedGenerator,
    analyzer: ScriptedAnalyzer | None = None,
    database: ScriptedDatabase | None = None,
) -> httpx.AsyncClient:
    database = database or ScriptedDatabase(DB_TABLES, [])
    flow = QueryFlow(generator, analyzer or ScriptedAnalyzer([]), database, TERMS_FOR_TEST, LIMITS)
    app = FastAPI()
    app.include_router(create_router(flow, Lookup(database, TERMS_FOR_TEST), "zzz-model"))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# --- QRY-R001 · 설계서 2.3 입력 검증 -------------------------------------------


@pytest.mark.parametrize("question", ["", "   ", "가" * 301], ids=["empty", "blank", "301"])
async def test_qry_r001_question_that_does_not_fit_is_422_with_the_reason(question: str) -> None:
    """QRY-R001 맞지 않는 질문은 흐름을 시작하지 않고 422, 본문은 `{"detail": 사유}` 다.

    사유는 흐름이 돌려준 것 그대로다 — 고정 문구로 바꾸거나 빠뜨리지 않는다 (설계서 2.3).
    """
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1")])
    async with client_for(generator) as client:
        response = await client.post("/api/queries", json={"question": question})
    # 흐름이 돌려준 사유를 그대로 옮기는지 본다. 문구는 규칙 테스트의 몫이라 적지 않는다.
    reason = QueryFlow(
        ScriptedGenerator([]),
        ScriptedAnalyzer([]),
        ScriptedDatabase(DB_TABLES, []),
        TERMS_FOR_TEST,
        LIMITS,
    ).start(Question(question))
    assert_reason(reason)
    assert response.status_code == 422
    assert response.json() == {"detail": reason}
    assert generator.calls == []


async def test_qry_r001_question_of_300_chars_is_accepted() -> None:
    """QRY-R001 300자 질문은 받는다 — 위 422 의 짝."""
    database = ScriptedDatabase(DB_TABLES, [QueryResult(("zzz_c",), ())])
    async with client_for(
        ScriptedGenerator([GeneratedSql("zzz sql 1")]), ScriptedAnalyzer([PASSING]), database
    ) as client:
        response = await client.post("/api/queries", json={"question": "가" * 300})
    assert response.status_code == 200


async def test_question_text_goes_to_the_flow_unchanged() -> None:
    """질문 글은 고치지 않고 그대로 흐름에 넘긴다 — 앞뒤 공백도 그대로다 (설계서 2.3)."""
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1")])
    database = ScriptedDatabase(DB_TABLES, [QueryResult(("zzz_c",), ())])
    async with client_for(generator, ScriptedAnalyzer([PASSING]), database) as client:
        await client.post("/api/queries", json={"question": "  zzz 지역별 매출 \n"})
    assert generator.calls[0].question == Question("  zzz 지역별 매출 \n")


# --- QRY-R012 · 설계서 2.2 SSE -------------------------------------------------


async def test_qry_r012_steps_are_sent_as_sse_events_in_order() -> None:
    """QRY-R012 질의 단계를 일어난 순서대로 SSE 이벤트로 보낸다.

    이벤트는 `event:` · `data:` 두 줄이다. 생성됨 · 검증됨 · 거부됨 · 완료 넷이 나오고, 완료의
    값은 JSON 의 문자열 · 정수 · 실수 · null 로 옮긴다.
    """
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    database = ScriptedDatabase(
        DB_TABLES,
        [
            ExecutionFailure(ExecutionFailureKind.REFUSED, "zzz 실행 거부"),
            QueryResult(
                ("zzz_a", "zzz_b", "zzz_c", "zzz_d"),
                (("zzz 값", 3, 1.5, None), ("zzz 둘째", -2, 0.25, "zzz 끝")),
            ),
        ],
    )
    async with client_for(generator, ScriptedAnalyzer([PASSING, PASSING]), database) as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})

    assert response.status_code == 200
    events = read_sse(response.text)
    assert events == [
        ("generated", {"attempt": 1, "sql": "zzz sql 1"}),
        ("validated", {"sql": "zzz sql 1"}),
        ("rejected", {"attempt": 1, "stage": "execute", "reason": "zzz 실행 거부"}),
        ("generated", {"attempt": 2, "sql": "zzz sql 2"}),
        ("validated", {"sql": "zzz sql 2"}),
        (
            "done",
            {
                "columns": ["zzz_a", "zzz_b", "zzz_c", "zzz_d"],
                "rows": [["zzz 값", 3, 1.5, None], ["zzz 둘째", -2, 0.25, "zzz 끝"]],
                "truncated": False,
            },
        ),
    ]
    # 파이썬에서 3 == 3.0 이 참이라, 정수 · 실수로 옮겼는지는 따로 본다.
    first_row = events[-1][1]["rows"][0]
    assert type(first_row[1]) is int
    assert type(first_row[2]) is float


async def test_qry_r012_generate_stage_is_its_wire_name() -> None:
    """QRY-R012 출력 형식 실패로 거부되면 `stage` 는 `generate` 다 (설계서 2.2).

    `execute` 는 위 테스트가, `validate` 는 아래 테스트가 본다.
    """
    generator = ScriptedGenerator(
        [
            GenerationFailure(GenerationFailureKind.FORMAT, "zzz 형식 세부"),
            GeneratedSql("zzz sql 2"),
        ]
    )
    database = ScriptedDatabase(DB_TABLES, [QueryResult(("zzz_c",), ())])
    async with client_for(generator, ScriptedAnalyzer([PASSING]), database) as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    name, data = read_sse(response.text)[0]
    assert (name, data["stage"]) == ("rejected", "generate")


async def test_qry_r012_validate_stage_is_its_wire_name() -> None:
    """QRY-R012 판정에서 거부되면 `stage` 는 `validate` 다 (설계서 2.2)."""
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    analyzer = ScriptedAnalyzer([replace(PASSING, is_query=False), PASSING])
    database = ScriptedDatabase(DB_TABLES, [QueryResult(("zzz_c",), ())])
    async with client_for(generator, analyzer, database) as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    name, data = read_sse(response.text)[1]
    assert (name, data["stage"]) == ("rejected", "validate")


async def test_qry_r012_failure_is_the_last_event_with_its_reason() -> None:
    """QRY-R012 실패하면 마지막 이벤트가 `failed` 하나이고 `reason` 만 담는다."""
    generator = ScriptedGenerator(
        [GenerationFailure(GenerationFailureKind.CONNECTION, "zzz 연결 거부")]
    )
    async with client_for(generator) as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    events = read_sse(response.text)
    assert len(events) == 1
    name, failed = events[0]
    assert name == "failed"
    assert list(failed) == ["reason"]
    assert "zzz 연결 거부" in failed["reason"]


async def test_qry_r005_truncated_result_is_marked_in_done() -> None:
    """QRY-R005 잘린 결과면 `done` 의 `truncated` 가 true 다 — 위 false 의 짝."""
    rows = ((1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,))
    database = ScriptedDatabase(DB_TABLES, [QueryResult(("zzz_n",), rows)])
    async with client_for(
        ScriptedGenerator([GeneratedSql("zzz sql 1")]), ScriptedAnalyzer([PASSING]), database
    ) as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    assert read_sse(response.text)[-1] == (
        "done",
        {"columns": ["zzz_n"], "rows": [[1], [2], [3], [4], [5], [6], [7]], "truncated": True},
    )


async def test_sse_response_asks_proxies_not_to_buffer() -> None:
    """SSE 응답은 이벤트 스트림이다 (설계서 2.2).

    프록시가 이벤트를 모았다가 보내지 않게 캐시 · 버퍼링을 끈다.
    """
    generator = ScriptedGenerator(
        [GenerationFailure(GenerationFailureKind.CONNECTION, "zzz 연결 거부")]
    )
    async with client_for(generator) as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"


# --- 설계서 2.4 보조 조회 ------------------------------------------------------


async def test_qry_r017_schema_is_the_described_tables_in_database_order() -> None:
    """QRY-R017 `/api/schema` 는 DB 순서의 표 · 열을 업무 설명과 함께 돌려준다."""
    async with client_for(ScriptedGenerator([])) as client:
        response = await client.get("/api/schema")
    assert response.status_code == 200
    assert response.json() == {
        "tables": [
            {
                "name": "zzz_sales",
                "description": "zzz 매출 표",
                "columns": [
                    {"name": "zzz_c", "type": "REAL", "description": ""},
                    {"name": "zzz_a", "type": "INTEGER", "description": "zzz 끝 열"},
                ],
            },
            {
                "name": "zzz_alpha",
                "description": "",
                "columns": [{"name": "zzz_d", "type": "TEXT", "description": ""}],
            },
        ]
    }


async def test_examples_are_the_terms_example_questions_in_order() -> None:
    """`/api/examples` 는 용어의 예시 질문을 그 순서대로 돌려준다 (설계서 2.4)."""
    async with client_for(ScriptedGenerator([])) as client:
        response = await client.get("/api/examples")
    assert response.status_code == 200
    assert response.json() == {"questions": ["zzz 둘째 질문", "zzz 첫 질문"]}


async def test_health_reports_the_model_name() -> None:
    """`/api/health` 는 상태와 조립 루트에서 받은 모델 이름을 돌려준다 (설계서 2.4)."""
    async with client_for(ScriptedGenerator([])) as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": "zzz-model"}
