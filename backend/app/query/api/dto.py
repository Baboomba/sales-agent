"""요청 · 응답 · SSE 이벤트의 모양 (설계서 2.2 · 2.3 · 2.4).

모델을 바깥 모양으로 옮기는 일은 여기서만 한다. 판단하지 않는다.
"""

from __future__ import annotations

from typing import assert_never

from pydantic import BaseModel

from app.query.model.question import Table
from app.query.model.run import Completed, Failed, Generated, QueryStep, Rejected, Validated


class QueryRequest(BaseModel):
    question: str


class ColumnDto(BaseModel):
    name: str
    type: str
    description: str


class TableDto(BaseModel):
    name: str
    description: str
    columns: list[ColumnDto]


class SchemaResponse(BaseModel):
    tables: list[TableDto]


class ExamplesResponse(BaseModel):
    questions: list[str]


class HealthResponse(BaseModel):
    status: str
    model: str


def schema_response(tables: tuple[Table, ...]) -> SchemaResponse:
    """QRY-R017 표 · 열을 업무 설명과 함께 (설계서 2.4)."""
    return SchemaResponse(
        tables=[
            TableDto(
                name=table.name,
                description=table.description,
                columns=[
                    ColumnDto(name=column.name, type=column.type, description=column.description)
                    for column in table.columns
                ],
            )
            for table in tables
        ]
    )


def examples_response(questions: tuple[str, ...]) -> ExamplesResponse:
    return ExamplesResponse(questions=list(questions))


def health_response(model_name: str) -> HealthResponse:
    return HealthResponse(status="ok", model=model_name)


def step_event(step: QueryStep) -> tuple[str, dict[str, object]]:
    """질의 단계를 SSE 이벤트의 이름과 `data` 로 옮긴다 (설계서 2.2)."""
    match step:
        case Generated(attempt=attempt, sql=sql):
            return "generated", {"attempt": attempt, "sql": sql}
        case Rejected(attempt=attempt, stage=stage, reason=reason):
            return "rejected", {"attempt": attempt, "stage": stage.value, "reason": reason}
        case Validated(sql=sql):
            return "validated", {"sql": sql}
        case Completed(result=result):
            return "done", {
                "columns": list(result.columns),
                "rows": [list(row) for row in result.rows],
                "truncated": result.truncated,
            }
        case Failed(reason=reason):
            return "failed", {"reason": reason}
        case _:
            assert_never(step)
