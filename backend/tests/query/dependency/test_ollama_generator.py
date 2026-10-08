"""생성기 구현. 언어 모델의 출력 · 바깥 오류를 생성 SQL · 생성 실패로 제대로 옮기는지,
받은 모델을 프롬프트에 싣는지 본다. 언어 모델은 부르지 않는다 (NFR-005).

재생성할지 · 어떤 사유로 끝낼지는 규칙 테스트가 본다 (테스트 규칙 7.1).
"""

from __future__ import annotations

from dataclasses import replace

import httpx
import pytest
from ollama import ResponseError

from app.query.dependency.impl.ollama_generator import OllamaSqlGenerator
from app.query.model.failure import GenerationFailure, GenerationFailureKind
from app.query.model.question import Column, Question, Table
from app.query.model.sql import GeneratedSql
from app.query.model.terms import TERMS, ExampleQuery, Terms
from tests.query.fake import ScriptedModel
from tests.query.rules.support import assert_reason

TABLES = (
    Table(
        "zzz_first",
        (
            Column("zzz_col_a", "INTEGER", "zzz 첫 열 설명"),
            Column("zzz_col_a2", "TEXT", "zzz 가운데 열 설명"),
            Column("zzz_col_a3", "REAL", "zzz 셋째 열 설명"),
        ),
        "zzz 첫 표 설명",
    ),
    Table("zzz_middle", (Column("zzz_col_b", "TEXT"),)),
    Table("zzz_last", (Column("zzz_col_c", "TEXT", "zzz 끝 열 설명"),), "zzz 끝 표 설명"),
)
TERMS_FOR_TEST: Terms = replace(
    TERMS,
    revenue_definition="zzz 매출 정의",
    order_count_definition="zzz 주문 건수 정의",
    example_queries=(
        ExampleQuery("zzz 첫 예시 질문", "SELECT zzz_first_example"),
        ExampleQuery("zzz 끝 예시 질문", "SELECT zzz_last_example"),
    ),
)


async def generate(
    replies: list[str | Exception], *, attempt: int = 2, last_reason: str | None = None
) -> tuple[GeneratedSql | GenerationFailure, ScriptedModel]:
    model = ScriptedModel(replies)
    result = await OllamaSqlGenerator(model).generate(
        Question("zzz 질문"), TABLES, TERMS_FOR_TEST, attempt=attempt, last_reason=last_reason
    )
    return result, model


# --- QRY-R010 출력 형식 ---------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        '{"sql": "SELECT zzz FROM t"}',
        '```json\n{"sql": "SELECT zzz FROM t"}\n```',
        '```\n{"sql": "SELECT zzz FROM t"}\n```',
        '  {"sql": "  SELECT zzz FROM t  "}  ',
    ],
    ids=["json", "json-fence", "plain-fence", "spaces"],
)
async def test_qry_r010_sql_is_taken_from_json_output(reply: str) -> None:
    """QRY-R010 출력 `{"sql": "..."}` 에서 SQL 을 꺼낸다. 코드 펜스는 걷고, 앞뒤 공백은 뗀다."""
    result, _ = await generate([reply], attempt=2)
    assert result == GeneratedSql(attempt=2, text="SELECT zzz FROM t")


async def test_generated_sql_carries_the_attempt_it_was_given() -> None:
    result, _ = await generate(['{"sql": "SELECT 1"}'], attempt=3)
    assert result == GeneratedSql(attempt=3, text="SELECT 1")


@pytest.mark.parametrize(
    "reply",
    [
        "SELECT zzz FROM t",
        '["SELECT zzz FROM t"]',
        '{"query": "SELECT zzz FROM t"}',
        '{"sql": ""}',
        '{"sql": "   "}',
        '{"sql": 1}',
    ],
    ids=["not-json", "not-object", "no-sql-key", "empty", "spaces-only", "not-text"],
)
async def test_qry_r010_bad_output_becomes_a_format_failure_with_a_detail(reply: str) -> None:
    """QRY-R010 JSON 이 아니거나 `sql` 이 없거나 비면 출력 형식 실패다.

    세부는 생성기가 짓는 안내다.
    """
    result, _ = await generate([reply])
    assert isinstance(result, GenerationFailure)
    assert result.kind is GenerationFailureKind.FORMAT
    assert_reason(result.detail)


# --- QRY-R013 모델 서버 장애 ----------------------------------------------


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (httpx.ReadTimeout("zzz read timed out"), GenerationFailureKind.TIMEOUT),
        (ResponseError("model 'zzz-model' not found"), GenerationFailureKind.ERROR_RESPONSE),
        (httpx.ConnectError("zzz connection refused"), GenerationFailureKind.CONNECTION),
        (ConnectionError("zzz connection reset"), GenerationFailureKind.CONNECTION),
    ],
    ids=["timeout", "error-response", "httpx-connect", "connection"],
)
async def test_qry_r013_outage_becomes_its_kind_with_the_outside_detail(
    error: Exception, kind: GenerationFailureKind
) -> None:
    """QRY-R013 연결 실패 · 오류 응답 · 시간 초과를 각각의 생성 실패로 옮긴다.

    세부는 바깥이 준 말이다.
    """
    result, _ = await generate([error])
    assert isinstance(result, GenerationFailure)
    assert result.kind is kind
    assert "zzz" in result.detail


async def test_unexpected_error_is_not_turned_into_a_failure() -> None:
    """예상하지 못한 오류는 실패 모델로 숨기지 않는다.

    유스케이스 입구의 안전망이 받는다 (QRY-R012).
    """
    with pytest.raises(ValueError):
        await generate([ValueError("zzz bug")])


# --- 프롬프트 — 받은 모델을 싣는다 (설계서 5.2) ----------------------------


@pytest.mark.parametrize(
    "expected",
    [
        "zzz 질문",
        "zzz_first",
        "zzz 첫 표 설명",
        "zzz_col_a",
        "zzz 첫 열 설명",
        "zzz_col_a2",
        "zzz 가운데 열 설명",
        "zzz_col_a3",
        "zzz 셋째 열 설명",
        "zzz_middle",
        "zzz_col_b",
        "zzz_last",
        "zzz 끝 표 설명",
        "zzz_col_c",
        "zzz 끝 열 설명",
        "zzz 매출 정의",
        "zzz 주문 건수 정의",
        "zzz 첫 예시 질문",
        "SELECT zzz_first_example",
        "zzz 끝 예시 질문",
        "SELECT zzz_last_example",
    ],
)
async def test_prompt_carries_the_question_tables_and_terms(expected: str) -> None:
    """프롬프트에 질문, 모든 표 · 열의 이름과 업무 설명, 용어의 정의, 모든 예시 질의가 실린다.

    표 · 열 · 예시 질의는 처음 · 가운데 · 끝을 다 본다.
    """
    _, model = await generate(['{"sql": "SELECT 1"}'])
    assert expected in model.prompts[0]


async def test_prompt_carries_the_last_reason_when_regenerating() -> None:
    """다시 생성할 때는 직전 실패 사유가 프롬프트에 실린다 (QRY-R006 의 사유가 넘어가는 자리)."""
    _, model = await generate(['{"sql": "SELECT 1"}'], last_reason="zzz 직전 사유")
    assert "zzz 직전 사유" in model.prompts[0]


async def test_prompt_does_not_print_a_missing_reason() -> None:
    """위 테스트의 짝 — 직전 실패가 없으면 사유를 싣지 않는다.

    빈 사유를 `None` 글자로 찍지 않는다.
    """
    _, model = await generate(['{"sql": "SELECT 1"}'], last_reason=None)
    assert "None" not in model.prompts[0]
