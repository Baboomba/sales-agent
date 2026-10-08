"""그래프 · API 테스트가 쓰는 가짜 포트.

언어 모델과 DB 없이 그래프의 분기를 확인하기 위한 것이다 (NFR-005).
"""

from __future__ import annotations

from collections.abc import Iterable

from app.query.model import Column, QueryResult, Table
from app.query.ports import ExecutionError, GeneratorUnavailable

TABLES = (
    Table(
        name="stores",
        columns=(Column("store_id", "INTEGER"), Column("name", "TEXT"), Column("region", "TEXT")),
    ),
    Table(
        name="orders",
        columns=(Column("order_id", "INTEGER"), Column("store_id", "INTEGER")),
    ),
)


class ScriptedGenerator:
    """미리 정한 출력을 차례로 돌려주고, 받은 프롬프트를 기록한다.

    출력 자리에 GeneratorUnavailable 을 두면 그 차례에 연결 실패를 흉내 낸다.
    """

    def __init__(self, outputs: Iterable[str | GeneratorUnavailable]) -> None:
        self._outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self._outputs:
            raise AssertionError("생성기가 예상보다 많이 불렸다")
        output = self._outputs.pop(0)
        if isinstance(output, GeneratorUnavailable):
            raise output
        return output

    @property
    def calls(self) -> int:
        return len(self.prompts)


class FakeDatabase:
    """SQL 마다 정해 둔 결과나 오류를 돌려준다. 정하지 않은 SQL 은 기본 결과다."""

    def __init__(
        self,
        results: dict[str, QueryResult | ExecutionError] | None = None,
        default: QueryResult | None = None,
    ) -> None:
        self._results = results or {}
        self._default = default or QueryResult(columns=("n",), rows=((1,),))
        self.executed: list[str] = []

    def schema(self) -> tuple[Table, ...]:
        return TABLES

    def execute(self, sql: str) -> QueryResult:
        self.executed.append(sql)
        result = self._results.get(sql, self._default)
        if isinstance(result, ExecutionError):
            raise result
        return result


def sql_json(sql: str) -> str:
    """모델이 정상적으로 낸 출력의 모양."""
    import json

    return json.dumps({"sql": sql}, ensure_ascii=False)
