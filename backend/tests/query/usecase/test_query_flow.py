"""질의 흐름. 가짜 생성기 · SQL 분석기 · 매출 DB 로 어느 경로로 가서 무엇을 내는지 본다.

판정 · 사유의 문구는 규칙 테스트가 본다. 여기서는 사유가 어디로 넘어가는지만 본다.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
from dataclasses import replace

import pytest

from app.query.model.failure import (
    ExecutionFailure,
    ExecutionFailureKind,
    GenerationFailure,
    GenerationFailureKind,
    QueryLimits,
    Stage,
)
from app.query.model.question import Column, Question, Table
from app.query.model.run import (
    Completed,
    Failed,
    Generated,
    QueryResult,
    QueryStep,
    Rejected,
    Validated,
)
from app.query.model.sql import GeneratedSql, SqlShape, TableRef
from app.query.model.terms import TERMS
from app.query.usecase.query_flow import QueryFlow
from tests.query.fake import ScriptedAnalyzer, ScriptedDatabase, ScriptedGenerator
from tests.query.support import assert_reason, passing_shape

LIMITS = QueryLimits(
    max_attempts=3, row_limit=7, generation_timeout_seconds=13, query_timeout_seconds=4
)
QUESTION = Question("zzz 지역별 매출")

# DB 가 낸 표 목록 — 처음 · 가운데 · 끝. 설명은 비어 있다.
DB_TABLES = (
    Table("zzz_first", (Column("zzz_a", "TEXT"),)),
    Table("zzz_mid", (Column("zzz_b", "INTEGER"),)),
    Table("zzz_last", (Column("zzz_c", "REAL"),)),
)
# 용어에는 DB 에 없는 표의 설명도 있다 — 허용된 표가 되지 않아야 한다.
TERMS_FOR_TEST = replace(
    TERMS,
    table_descriptions={"zzz_first": "zzz 첫 표", "zzz_absent": "zzz 없는 표"},
    column_descriptions={("zzz_last", "zzz_c"): "zzz 끝 열"},
)

# 판정을 통과하는 SQL 구성. 바깥 행 상한 3 은 상한(7) 이하라 붙일 행 상한이 없다.
PASSING = passing_shape("zzz_first")
WRITING = replace(PASSING, is_query=False)
RESULT = QueryResult(("zzz_col",), (("zzz 값",),))


def make_flow(
    generator: ScriptedGenerator, analyzer: ScriptedAnalyzer, database: ScriptedDatabase
) -> QueryFlow:
    return QueryFlow(generator, analyzer, database, TERMS_FOR_TEST, LIMITS)


def database(results: Iterable[QueryResult | ExecutionFailure | Exception]) -> ScriptedDatabase:
    return ScriptedDatabase(DB_TABLES, results)


async def run(flow: QueryFlow, question: Question = QUESTION) -> list[QueryStep]:
    started = flow.start(question)
    assert not isinstance(started, str)
    return [step async for step in started]


# --- QRY-R012 · QRY-R011 성공 경로 ---------------------------------------


async def test_qry_r012_success_steps_are_generated_validated_completed() -> None:
    """QRY-R012 성공하면 생성됨 → 검증됨 → 완료 순서다. 완료는 DB 가 낸 값 그대로다 (QRY-R011)."""
    flow = make_flow(
        ScriptedGenerator([GeneratedSql("zzz sql 1")]),
        ScriptedAnalyzer([PASSING]),
        database([RESULT]),
    )
    assert await run(flow) == [
        Generated(attempt=1, sql="zzz sql 1"),
        Validated(sql="zzz sql 1"),
        Completed(QueryResult(("zzz_col",), (("zzz 값",),), truncated=False)),
    ]


async def test_qry_r011_generator_is_called_once_on_completion() -> None:
    """QRY-R011 실행 뒤에는 생성기를 부르지 않는다. 완료면 생성은 한 번뿐이다."""
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    await run(make_flow(generator, ScriptedAnalyzer([PASSING]), database([RESULT])))
    assert len(generator.calls) == 1


async def test_qry_r017_generator_gets_the_question_and_described_tables() -> None:
    """QRY-R017 생성기는 질문과, DB 의 표에 규칙이 용어의 설명을 붙인 목록을 받는다.

    첫 생성에는 직전 실패 사유가 없다.
    """
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1")])
    await run(make_flow(generator, ScriptedAnalyzer([PASSING]), database([RESULT])))
    call = generator.calls[0]
    assert call.question == Question("zzz 지역별 매출")
    assert call.tables == (
        Table("zzz_first", (Column("zzz_a", "TEXT", ""),), "zzz 첫 표"),
        Table("zzz_mid", (Column("zzz_b", "INTEGER", ""),), ""),
        Table("zzz_last", (Column("zzz_c", "REAL", "zzz 끝 열"),), ""),
    )
    assert call.terms == TERMS_FOR_TEST
    assert call.last_reason is None


# --- QRY-R005 행 상한 --------------------------------------------------------


async def test_qry_r005_without_a_limit_to_attach_the_generated_text_is_executed() -> None:
    """QRY-R005 붙일 행 상한이 없으면 생성 SQL 글을 그대로 실행하고, 상한+1 행을 가져온다."""
    analyzer = ScriptedAnalyzer([PASSING])
    db = database([RESULT])
    await run(make_flow(ScriptedGenerator([GeneratedSql("zzz sql 1")]), analyzer, db))
    assert analyzer.limit_calls == []
    assert db.executed == [("zzz sql 1", 8)]


async def test_qry_r005_sql_with_the_attached_limit_is_validated_and_executed() -> None:
    """QRY-R005 바깥 행 상한이 없으면 상한+1 을 붙인 SQL 이 검증됨 단계의 SQL 이다.

    실행하는 것도 그 SQL 이다.
    """
    analyzer = ScriptedAnalyzer([replace(PASSING, outer_limit=None)], ["zzz sql 1 limited"])
    db = database([RESULT])
    steps = await run(make_flow(ScriptedGenerator([GeneratedSql("zzz sql 1")]), analyzer, db))
    assert steps[1] == Validated(sql="zzz sql 1 limited")
    assert analyzer.limit_calls == [("zzz sql 1", 8)]
    assert db.executed == [("zzz sql 1 limited", 8)]


async def test_qry_r005_rows_over_the_limit_are_cut_and_marked_truncated() -> None:
    """QRY-R005 DB 가 상한+1 행을 내면 완료에는 상한만큼만 담고 잘렸다고 표시한다."""
    rows = ((1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,))
    flow = make_flow(
        ScriptedGenerator([GeneratedSql("zzz sql 1")]),
        ScriptedAnalyzer([PASSING]),
        database([QueryResult(("zzz_n",), rows)]),
    )
    steps = await run(flow)
    assert steps[-1] == Completed(
        QueryResult(("zzz_n",), ((1,), (2,), (3,), (4,), (5,), (6,), (7,)), truncated=True)
    )


async def test_qry_r014_bytes_in_the_result_are_replaced() -> None:
    """QRY-R014 완료의 바이트 값은 `<binary>` 로 바뀌고, 다른 값은 그대로다."""
    flow = make_flow(
        ScriptedGenerator([GeneratedSql("zzz sql 1")]),
        ScriptedAnalyzer([PASSING]),
        database([QueryResult(("zzz_a", "zzz_b"), (("zzz 값", b"\x00zzz"),))]),
    )
    steps = await run(flow)
    assert steps[-1] == Completed(QueryResult(("zzz_a", "zzz_b"), (("zzz 값", "<binary>"),)))


# --- QRY-R006 · QRY-R002 · QRY-R010 · QRY-R004 재생성 ------------------------


async def test_qry_r006_write_sql_is_regenerated_with_the_reason_and_succeeds_second() -> None:
    """QRY-R006 첫 생성이 쓰기 SQL 이면 판정에서 거부된다.

    그 사유를 붙여 다시 생성해 두 번째로 성공한다.
    """
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    analyzer = ScriptedAnalyzer([WRITING, PASSING])
    steps = await run(make_flow(generator, analyzer, database([RESULT])))

    assert steps[0] == Generated(attempt=1, sql="zzz sql 1")
    rejected = steps[1]
    assert isinstance(rejected, Rejected)
    assert (rejected.attempt, rejected.stage) == (1, Stage.VALIDATE)
    assert_reason(rejected.reason)
    assert steps[2:] == [
        Generated(attempt=2, sql="zzz sql 2"),
        Validated(sql="zzz sql 2"),
        Completed(RESULT),
    ]
    assert analyzer.analyzed == ["zzz sql 1", "zzz sql 2"]
    assert generator.calls[1].last_reason == rejected.reason


async def test_qry_r002_parse_error_is_regenerated() -> None:
    """QRY-R002 분석 오류(닫히지 않은 따옴표 등)가 있는 SQL 은 거부하고 다시 생성한다.

    흐름이 끊기지 않는다.
    """
    analyzer = ScriptedAnalyzer([replace(PASSING, parse_error="zzz 닫히지 않은 따옴표"), PASSING])
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    steps = await run(make_flow(generator, analyzer, database([RESULT])))

    rejected = steps[1]
    assert isinstance(rejected, Rejected)
    assert (rejected.attempt, rejected.stage) == (1, Stage.VALIDATE)
    assert "zzz 닫히지 않은 따옴표" in rejected.reason
    assert steps[-1] == Completed(RESULT)


async def test_qry_r004_only_tables_in_the_database_are_allowed() -> None:
    """QRY-R004 · QRY-R017 허용된 표는 DB 의 표 목록이다.

    용어에만 있는 표는 거부하고, DB 의 끝 표는 통과한다.
    """
    analyzer = ScriptedAnalyzer(
        [
            replace(PASSING, tables=(TableRef("zzz_absent"),)),
            replace(PASSING, tables=(TableRef("zzz_last"),)),
        ]
    )
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    steps = await run(make_flow(generator, analyzer, database([RESULT])))

    rejected = steps[1]
    assert isinstance(rejected, Rejected)
    assert "zzz_absent" in rejected.reason
    assert steps[3] == Validated(sql="zzz sql 2")


async def test_qry_r006_execution_failure_is_regenerated_with_the_reason() -> None:
    """QRY-R006 실행 실패도 사유를 붙여 다시 생성한다. 사유에는 DB 가 준 세부가 남는다."""
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    db = database([ExecutionFailure(ExecutionFailureKind.REFUSED, "zzz 실행 거부"), RESULT])
    steps = await run(make_flow(generator, ScriptedAnalyzer([PASSING, PASSING]), db))

    assert steps[:2] == [Generated(attempt=1, sql="zzz sql 1"), Validated(sql="zzz sql 1")]
    rejected = steps[2]
    assert isinstance(rejected, Rejected)
    assert (rejected.attempt, rejected.stage) == (1, Stage.EXECUTE)
    assert "zzz 실행 거부" in rejected.reason
    assert steps[3:] == [
        Generated(attempt=2, sql="zzz sql 2"),
        Validated(sql="zzz sql 2"),
        Completed(RESULT),
    ]
    assert generator.calls[1].last_reason == rejected.reason


@pytest.mark.parametrize(
    ("failure", "first", "second"),
    [
        (
            ExecutionFailure(ExecutionFailureKind.MISSING_ALIAS, "zzz 열 없음", alias="zq"),
            "zq",
            "JOIN",
        ),
        (ExecutionFailure(ExecutionFailureKind.TIMEOUT, "zzz 중단"), "4", "가벼운"),
    ],
    ids=["missing_alias", "timeout"],
)
async def test_qry_r015_qry_r009_execution_failure_reason_comes_from_the_rule(
    failure: ExecutionFailure, first: str, second: str
) -> None:
    """QRY-R015 · QRY-R009 실행 실패의 사유는 DB 의 세부 글이 아니라 규칙이 지은 사유다.

    별칭의 표 없음이면 별칭(세부 글에 없다)과 JOIN 안내, 시간 초과면 제한 시간(4초)과
    더 가벼운 질의 안내가 다음 생성에 넘어간다.
    """
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    db = database([failure, RESULT])
    steps = await run(make_flow(generator, ScriptedAnalyzer([PASSING, PASSING]), db))

    rejected = steps[2]
    assert isinstance(rejected, Rejected)
    assert first in rejected.reason
    assert second in rejected.reason
    assert generator.calls[1].last_reason == rejected.reason


async def test_qry_r010_format_failure_is_regenerated_with_the_detail() -> None:
    """QRY-R010 출력 형식 실패면 생성됨 없이 거부됨을 내고, 세부를 사유로 붙여 다시 생성한다."""
    generator = ScriptedGenerator(
        [
            GenerationFailure(GenerationFailureKind.FORMAT, "zzz 형식 세부"),
            GeneratedSql("zzz sql 2"),
        ]
    )
    steps = await run(make_flow(generator, ScriptedAnalyzer([PASSING]), database([RESULT])))

    rejected = steps[0]
    assert isinstance(rejected, Rejected)
    assert (rejected.attempt, rejected.stage) == (1, Stage.GENERATE)
    assert "zzz 형식 세부" in rejected.reason
    assert steps[1:] == [
        Generated(attempt=2, sql="zzz sql 2"),
        Validated(sql="zzz sql 2"),
        Completed(RESULT),
    ]
    assert generator.calls[1].last_reason == rejected.reason


# --- QRY-R007 · QRY-R013 실패로 끝남 ----------------------------------------


async def test_qry_r007_three_failures_end_with_failed_and_the_last_reason() -> None:
    """QRY-R007 세 번 모두 실패하면 마지막 질의 단계가 실패이고, 마지막 사유를 알린다.

    한도에 닿은 실패는 거부됨을 내지 않는다 (설계서 2.2).
    """
    generator = ScriptedGenerator(
        [GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2"), GeneratedSql("zzz sql 3")]
    )
    analyzer = ScriptedAnalyzer(
        [WRITING, WRITING, replace(PASSING, tables=(TableRef("zzz_last_absent"),))]
    )
    steps = await run(make_flow(generator, analyzer, database([])))

    assert len(steps) == 6
    assert isinstance(steps[3], Rejected)
    assert steps[4] == Generated(attempt=3, sql="zzz sql 3")
    failed = steps[5]
    assert isinstance(failed, Failed)
    assert "zzz_last_absent" in failed.reason
    assert len(generator.calls) == 3


@pytest.mark.parametrize(
    ("replies", "shapes", "results", "length"),
    [
        (
            [
                GenerationFailure(GenerationFailureKind.FORMAT, "zzz 마지막 1"),
                GenerationFailure(GenerationFailureKind.FORMAT, "zzz 마지막 2"),
                GenerationFailure(GenerationFailureKind.FORMAT, "zzz 마지막 3"),
            ],
            [],
            [],
            3,
        ),
        (
            [
                GeneratedSql("zzz sql 1"),
                GeneratedSql("zzz sql 2"),
                GeneratedSql("zzz sql 3"),
            ],
            [PASSING, PASSING, PASSING],
            [
                ExecutionFailure(ExecutionFailureKind.REFUSED, "zzz 마지막 1"),
                ExecutionFailure(ExecutionFailureKind.REFUSED, "zzz 마지막 2"),
                ExecutionFailure(ExecutionFailureKind.REFUSED, "zzz 마지막 3"),
            ],
            9,
        ),
    ],
    ids=["generate", "execute"],
)
async def test_qry_r007_limit_holds_when_generation_or_execution_fails(
    replies: list[GeneratedSql | GenerationFailure],
    shapes: list[SqlShape],
    results: list[QueryResult | ExecutionFailure],
    length: int,
) -> None:
    """QRY-R007 생성 · 실행이 세 번 모두 실패해도 실패로 끝내고 마지막 사유를 알린다.

    판정 쪽은 위 테스트가 본다. 한도에 닿은 실패는 거부됨을 내지 않는다 — 단계 수로 본다.
    """
    generator = ScriptedGenerator(replies)
    steps = await run(make_flow(generator, ScriptedAnalyzer(shapes), database(results)))

    assert len(steps) == length
    failed = steps[-1]
    assert isinstance(failed, Failed)
    assert "zzz 마지막 3" in failed.reason
    assert len(generator.calls) == 3
    # 세 번째 생성은 「직전」 실패의 사유만 받는다 — 쌓거나 첫 사유를 남기지 않는다.
    third = assert_reason(generator.calls[2].last_reason)
    assert "zzz 마지막 2" in third
    assert "zzz 마지막 1" not in third


async def test_qry_r007_limit_comes_from_the_query_limits() -> None:
    """QRY-R007 생성 최대 횟수가 2 면 두 번째 실패에서 끝난다 — 기본값 3 을 박은 구현을 가른다."""
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")])
    flow = QueryFlow(
        generator,
        ScriptedAnalyzer([WRITING, WRITING]),
        database([]),
        TERMS_FOR_TEST,
        replace(LIMITS, max_attempts=2),
    )
    steps = await run(flow)

    assert len(steps) == 4
    assert steps[2] == Generated(attempt=2, sql="zzz sql 2")
    assert isinstance(steps[3], Failed)
    assert len(generator.calls) == 2


@pytest.mark.parametrize(
    ("kind", "fragment"),
    [
        (GenerationFailureKind.CONNECTION, "zzz 장애 세부"),
        (GenerationFailureKind.ERROR_RESPONSE, "zzz 장애 세부"),
        (GenerationFailureKind.TIMEOUT, "13"),
    ],
)
async def test_qry_r013_model_server_outage_fails_without_regenerating(
    kind: GenerationFailureKind, fragment: str
) -> None:
    """QRY-R013 모델 서버 장애면 한도가 남아도 다시 생성하지 않고 실패 하나만 낸다.

    사유는 규칙이 지은 것이다 — 시간 초과면 세부 글이 아니라 생성 제한 시간(13초)이 남는다.
    """
    generator = ScriptedGenerator(
        [GenerationFailure(kind, "zzz 장애 세부"), GeneratedSql("zzz sql 2")]
    )
    steps = await run(make_flow(generator, ScriptedAnalyzer([PASSING]), database([RESULT])))

    assert len(steps) == 1
    assert isinstance(steps[0], Failed)
    assert fragment in steps[0].reason
    assert len(generator.calls) == 1


# --- QRY-R012 예상하지 못한 오류 ---------------------------------------------


async def test_qry_r012_generator_exception_ends_with_failed() -> None:
    """QRY-R012 생성기가 예상하지 못한 예외를 던져도 흐름 밖으로 새지 않고 마지막이 실패다.

    사유는 규칙이 정한 것이다 — 예외의 글(내부 경로 · SQL)을 사용자에게 내보내지 않는다.
    """
    flow = make_flow(
        ScriptedGenerator([RuntimeError("zzz 버그")]),
        ScriptedAnalyzer([PASSING]),
        database([RESULT]),
    )
    steps = await run(flow)
    assert len(steps) == 1
    assert isinstance(steps[0], Failed)
    assert_reason(steps[0].reason)
    assert "zzz 버그" not in steps[0].reason


async def test_qry_r012_exception_after_some_steps_ends_with_failed() -> None:
    """QRY-R012 단계를 낸 뒤에 예외가 나도 낸 단계는 그대로 두고, 마지막이 실패다."""
    flow = make_flow(
        ScriptedGenerator([GeneratedSql("zzz sql 1")]),
        ScriptedAnalyzer([PASSING]),
        database([RuntimeError("zzz 버그")]),
    )
    steps = await run(flow)
    assert steps[:2] == [Generated(attempt=1, sql="zzz sql 1"), Validated(sql="zzz sql 1")]
    assert len(steps) == 3
    assert isinstance(steps[2], Failed)
    assert_reason(steps[2].reason)
    assert "zzz 버그" not in steps[2].reason


async def test_unexpected_error_is_logged_with_its_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """예상하지 못한 오류는 버그라 로그를 남긴다 (코드 아키텍처 3절)."""
    flow = make_flow(
        ScriptedGenerator([RuntimeError("zzz 버그")]),
        ScriptedAnalyzer([PASSING]),
        database([RESULT]),
    )
    with caplog.at_level(logging.ERROR):
        await run(flow)
    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None


async def test_success_leaves_no_error_log(caplog: pytest.LogCaptureFixture) -> None:
    """위 테스트의 짝 — 성공하면 오류 로그가 없다. 늘 로그를 남기는 구현이 통과하지 않게."""
    flow = make_flow(
        ScriptedGenerator([GeneratedSql("zzz sql 1")]),
        ScriptedAnalyzer([PASSING]),
        database([RESULT]),
    )
    with caplog.at_level(logging.ERROR):
        await run(flow)
    assert caplog.records == []


# --- 입력 검증 · 표 목록 · 실행 자리 (설계서 2.1 · 2.3) -----------------------


async def test_qry_r001_question_that_does_not_fit_is_refused_without_starting() -> None:
    """QRY-R001 맞지 않는 질문이면 흐름을 시작하지 않고 사유를 돌려준다 (설계서 2.3)."""
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1")])
    flow = make_flow(generator, ScriptedAnalyzer([PASSING]), database([RESULT]))
    assert_reason(flow.start(Question("   ")))
    assert generator.calls == []


async def test_tables_are_read_once_when_the_flow_is_made() -> None:
    """표 목록은 유스케이스를 만들 때 한 번 읽고, 질문마다 다시 읽지 않는다 (설계서 2.1)."""
    db = database([RESULT, RESULT])
    flow = make_flow(
        ScriptedGenerator([GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2")]),
        ScriptedAnalyzer([PASSING, PASSING]),
        db,
    )
    assert db.table_reads == 1
    await run(flow)
    await run(flow, Question("zzz 다른 질문"))
    assert db.table_reads == 1


async def test_each_question_starts_from_the_first_attempt() -> None:
    """시도 번호 · 직전 실패 사유는 질문 하나의 것이다 (설계서 2.1).

    앞 질문의 재생성이 다음 질문에 남지 않는다.
    """
    generator = ScriptedGenerator(
        [GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2"), GeneratedSql("zzz sql 3")]
    )
    flow = make_flow(
        generator, ScriptedAnalyzer([WRITING, PASSING, PASSING]), database([RESULT, RESULT])
    )
    await run(flow)
    steps = await run(flow, Question("zzz 다른 질문"))

    assert steps[0] == Generated(attempt=1, sql="zzz sql 3")
    assert generator.calls[2].last_reason is None


async def test_questions_running_together_keep_their_own_state() -> None:
    """흐름 하나를 질문 여럿이 함께 써도 시도 번호 · 직전 실패 사유는 질문마다 따로다 (설계서 2.1).

    질문 A 가 거부된 자리에서 질문 B 를 끝까지 돌리고, 그다음 A 를 잇는다. B 도 한 번 거부된
    뒤 성공한다 — B 가 쓴 시도 수와 사유가 A 에 남으면 A 의 시도 번호와 사유가 어긋난다.
    """
    generator = ScriptedGenerator(
        [
            GeneratedSql("zzz a 1"),
            GeneratedSql("zzz b 1"),
            GeneratedSql("zzz b 2"),
            GeneratedSql("zzz a 2"),
        ]
    )
    analyzer = ScriptedAnalyzer(
        [WRITING, replace(PASSING, tables=(TableRef("zzz_b_absent"),)), PASSING, PASSING]
    )
    flow = make_flow(generator, analyzer, database([RESULT, RESULT]))
    a = flow.start(Question("zzz 질문 A"))
    assert not isinstance(a, str)
    assert await anext(a) == Generated(attempt=1, sql="zzz a 1")
    a_rejected = await anext(a)
    assert isinstance(a_rejected, Rejected)

    b_steps = await run(flow, Question("zzz 질문 B"))
    a_rest = [step async for step in a]

    assert b_steps[0] == Generated(attempt=1, sql="zzz b 1")
    b_rejected = b_steps[1]
    assert isinstance(b_rejected, Rejected)
    assert "zzz_b_absent" in b_rejected.reason
    assert b_steps[2:] == [
        Generated(attempt=2, sql="zzz b 2"),
        Validated("zzz b 2"),
        Completed(RESULT),
    ]
    assert generator.calls[1].last_reason is None
    assert generator.calls[2].last_reason == b_rejected.reason
    assert a_rest == [Generated(attempt=2, sql="zzz a 2"), Validated("zzz a 2"), Completed(RESULT)]
    assert generator.calls[3].last_reason == a_rejected.reason


async def test_execution_runs_off_the_event_loop_thread() -> None:
    """실행은 다른 스레드에서 한다 — 실행 제한 시간 동안 다른 질문이 멈추지 않게 (설계서 2.1)."""
    db = database([RESULT])
    await run(
        make_flow(ScriptedGenerator([GeneratedSql("zzz sql 1")]), ScriptedAnalyzer([PASSING]), db)
    )
    assert db.threads != [threading.get_ident()]
    assert len(db.threads) == 1
