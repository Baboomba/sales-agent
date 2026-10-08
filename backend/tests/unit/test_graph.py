"""Agent 그래프의 재생성 루프와 이벤트. 가짜 생성기 · 가짜 DB 로 분기를 확인한다."""

from __future__ import annotations

from app.query.graph import AgentSettings, SqlAgent
from app.query.model import Done, Event, Failed, Generated, QueryResult, Rejected, Validated
from app.query.ports import ExecutionError, GeneratorUnavailable
from tests.fakes import FakeDatabase, ScriptedGenerator, sql_json

SETTINGS = AgentSettings(max_attempts=3, row_limit=200)
GOOD_SQL = "SELECT region FROM stores LIMIT 10"


async def collect(agent: SqlAgent, question: str = "지역 목록") -> list[Event]:
    return [event async for event in agent.stream(question)]


def kinds(events: list[Event]) -> list[str]:
    return [event.type for event in events]


async def test_success_runs_generate_validate_execute_in_order() -> None:
    """QRY-R012 성공하면 generated → validated → done 순서다."""
    generator = ScriptedGenerator([sql_json(GOOD_SQL)])
    events = await collect(SqlAgent(generator, FakeDatabase(), SETTINGS))
    assert kinds(events) == ["generated", "validated", "done"]


async def test_qry_r011_generator_is_called_once_on_success() -> None:
    """QRY-R011 실행 뒤에는 모델을 부르지 않는다. 성공하면 생성은 한 번뿐이다."""
    generator = ScriptedGenerator([sql_json(GOOD_SQL)])
    await collect(SqlAgent(generator, FakeDatabase(), SETTINGS))
    assert generator.calls == 1


async def test_qry_r011_done_carries_database_values_unchanged() -> None:
    """QRY-R011 done 의 값은 DB 가 낸 값 그대로다."""
    result = QueryResult(columns=("region", "revenue"), rows=(("서울", 123456789),))
    database = FakeDatabase(default=result)
    events = await collect(SqlAgent(ScriptedGenerator([sql_json(GOOD_SQL)]), database, SETTINGS))
    done = events[-1]
    assert isinstance(done, Done)
    assert done.columns == ("region", "revenue")
    assert done.rows == (("서울", 123456789),)


async def test_qry_r006_rejected_sql_is_regenerated_with_reason() -> None:
    """QRY-R006 검증에 걸리면 사유를 프롬프트에 붙여 다시 생성하고, 두 번째로 성공한다."""
    generator = ScriptedGenerator([sql_json("DELETE FROM orders"), sql_json(GOOD_SQL)])
    events = await collect(SqlAgent(generator, FakeDatabase(), SETTINGS))

    assert kinds(events) == ["generated", "rejected", "generated", "validated", "done"]
    rejected = events[1]
    assert isinstance(rejected, Rejected)
    assert rejected.stage == "validate"
    assert rejected.reason in generator.prompts[1]
    assert rejected.reason not in generator.prompts[0]


async def test_qry_r006_execution_error_is_regenerated() -> None:
    """QRY-R006 실행 오류도 사유를 붙여 다시 생성한다."""
    bad = "SELECT nope FROM stores LIMIT 10"
    database = FakeDatabase(results={bad: ExecutionError("no such column: nope")})
    generator = ScriptedGenerator([sql_json(bad), sql_json(GOOD_SQL)])
    events = await collect(SqlAgent(generator, database, SETTINGS))

    rejected = [e for e in events if isinstance(e, Rejected)]
    assert [r.stage for r in rejected] == ["execute"]
    assert "no such column: nope" in generator.prompts[1]
    assert isinstance(events[-1], Done)


async def test_qry_r010_invalid_json_is_regenerated() -> None:
    """QRY-R010 JSON 이 아닌 출력은 생성 실패로 다뤄 다시 생성한다."""
    generator = ScriptedGenerator(["SELECT 1 이에요", sql_json(GOOD_SQL)])
    events = await collect(SqlAgent(generator, FakeDatabase(), SETTINGS))
    assert kinds(events) == ["rejected", "generated", "validated", "done"]
    first = events[0]
    assert isinstance(first, Rejected)
    assert first.stage == "generate"


async def test_qry_r007_gives_up_after_max_attempts_with_last_reason() -> None:
    """QRY-R007 세 번 모두 실패하면 failed 로 끝내고 마지막 사유를 알린다."""
    generator = ScriptedGenerator(
        [
            sql_json("DELETE FROM orders"),
            sql_json("DROP TABLE orders"),
            sql_json("SELECT 1; SELECT 2"),
        ]
    )
    events = await collect(SqlAgent(generator, FakeDatabase(), SETTINGS))

    assert generator.calls == 3
    failed = events[-1]
    assert isinstance(failed, Failed)
    assert "한 문장" in failed.reason
    assert sum(isinstance(e, Failed) for e in events) == 1


async def test_qry_r007_attempt_numbers_increase() -> None:
    """QRY-R007 이벤트의 시도 번호는 1 부터 올라간다."""
    generator = ScriptedGenerator([sql_json("DELETE FROM orders"), sql_json(GOOD_SQL)])
    events = await collect(SqlAgent(generator, FakeDatabase(), SETTINGS))
    attempts = [e.attempt for e in events if isinstance(e, Generated | Rejected)]
    assert attempts == [1, 1, 2]


async def test_qry_r013_unreachable_generator_fails_without_retry() -> None:
    """QRY-R013 모델 서버에 닿지 않으면 다시 시도하지 않고 바로 끝낸다."""
    generator = ScriptedGenerator([GeneratorUnavailable("connection refused")])
    events = await collect(SqlAgent(generator, FakeDatabase(), SETTINGS))

    assert generator.calls == 1
    assert kinds(events) == ["failed"]


async def test_qry_r005_validated_sql_is_what_gets_executed() -> None:
    """QRY-R005 실행되는 SQL 은 LIMIT 을 보정한 SQL 이다."""
    database = FakeDatabase()
    generator = ScriptedGenerator([sql_json("SELECT region FROM stores")])
    events = await collect(SqlAgent(generator, database, SETTINGS))

    validated = next(e for e in events if isinstance(e, Validated))
    assert database.executed == [validated.sql]
    assert validated.sql.endswith("LIMIT 200")


async def test_qry_r005_truncated_when_capped_and_full() -> None:
    """QRY-R005 상한을 붙였고 상한만큼 찼으면 잘렸다고 알린다."""
    rows = tuple((i,) for i in range(5))
    database = FakeDatabase(default=QueryResult(columns=("n",), rows=rows))
    agent = SqlAgent(
        ScriptedGenerator([sql_json("SELECT store_id FROM stores")]),
        database,
        AgentSettings(max_attempts=3, row_limit=5),
    )
    done = (await collect(agent))[-1]
    assert isinstance(done, Done)
    assert done.truncated is True


async def test_qry_r014_bytes_in_result_are_replaced() -> None:
    """QRY-R014 결과의 바이트 값은 <binary> 로 바뀐다."""
    database = FakeDatabase(default=QueryResult(columns=("blob",), rows=((b"\x00",),)))
    events = await collect(SqlAgent(ScriptedGenerator([sql_json(GOOD_SQL)]), database, SETTINGS))
    done = events[-1]
    assert isinstance(done, Done)
    assert done.rows == (("<binary>",),)
