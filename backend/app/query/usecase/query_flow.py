"""질의 흐름 — 질문 하나를 생성 · 판정 · 실행으로 옮긴다 (설계서 2.1 · 2.3).

판단은 규칙이 한다. 이 흐름은 규칙의 답을 따라 다음 단계로 옮기고, 단계마다 질의 단계를 낸다.
흐름을 이끄는 LangGraph 와 그 상태는 이 파일 밖으로 나가지 않는다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TypedDict, assert_never

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.query.dependency.sales_database import SalesDatabase
from app.query.dependency.sql_analyzer import SqlAnalyzer
from app.query.dependency.sql_generator import SqlGenerator
from app.query.model.failure import ExecutionFailure, GenerationFailure, QueryLimits, Stage
from app.query.model.question import Question
from app.query.model.run import (
    Completed,
    Failed,
    Generated,
    QueryStep,
    Rejected,
    Validated,
)
from app.query.model.sql import Refused
from app.query.model.terms import Terms
from app.query.rules.execution import execution_failure_reason
from app.query.rules.question import check_question
from app.query.rules.result import sanitize
from app.query.rules.retry import after_generation_failure, after_rejection, after_unexpected_error
from app.query.rules.row_limit import cap_rows, rows_to_fetch
from app.query.rules.sql import judge
from app.query.rules.terms import describe_tables

logger = logging.getLogger(__name__)

_GENERATE = "generate"
_VALIDATE = "validate"
_EXECUTE = "execute"


class _State(TypedDict, total=False):
    """질문 하나의 흐름 상태. 시도 번호 · 직전 실패 사유는 질문마다 처음부터다."""

    question: Question
    attempt: int
    last_reason: str | None
    sql: str  # 생성 SQL 글, 판정을 통과한 뒤에는 실행할 SQL 글
    step: QueryStep  # 방금 끝난 노드가 낸 질의 단계


class QueryFlow:
    def __init__(
        self,
        generator: SqlGenerator,
        analyzer: SqlAnalyzer,
        database: SalesDatabase,
        terms: Terms,
        limits: QueryLimits,
    ) -> None:
        self._generator = generator
        self._analyzer = analyzer
        self._database = database
        self._terms = terms
        self._limits = limits
        # 설계서 2.1 표 목록은 만들 때 한 번 읽는다. 그 이름들이 허용된 표다 (QRY-R004 · QRY-R017).
        self._tables = describe_tables(database.tables(), terms)
        self._allowed = frozenset(table.name for table in self._tables)
        self._graph = self._build()

    def start(self, question: Question) -> str | AsyncIterator[QueryStep]:
        """질문이 맞지 않으면 사유를, 맞으면 질의 단계의 흐름을 돌려준다 (QRY-R001, 설계서 2.3)."""
        reason = check_question(question)
        if reason is not None:
            return reason
        return self._steps(question)

    async def _steps(self, question: Question) -> AsyncIterator[QueryStep]:
        """QRY-R012 단계를 일어난 순서대로 낸다. 마지막은 완료나 실패 하나다."""
        initial: _State = {"question": question, "attempt": 0, "last_reason": None}
        try:
            async for chunk in self._graph.astream(initial, stream_mode="updates"):
                for update in chunk.values():
                    yield update["step"]
        except Exception:
            # 안전망. 예상한 실패는 의존성이 실패 모델로 돌려준다. 여기 오는 것은 버그다.
            logger.exception("질의 흐름에서 예상하지 못한 오류")
            yield after_unexpected_error()

    # --- 그래프 -----------------------------------------------------------

    def _build(self) -> CompiledStateGraph[_State, None, _State, _State]:
        graph = StateGraph(_State)
        graph.add_node(_GENERATE, self._generate)
        graph.add_node(_VALIDATE, self._validate)
        graph.add_node(_EXECUTE, self._execute)
        graph.add_edge(START, _GENERATE)
        for node in (_GENERATE, _VALIDATE, _EXECUTE):
            graph.add_conditional_edges(node, _route, [_GENERATE, _VALIDATE, _EXECUTE, END])
        return graph.compile()

    async def _generate(self, state: _State) -> _State:
        attempt = state["attempt"] + 1
        generated = await self._generator.generate(
            state["question"],
            self._tables,
            self._terms,
            last_reason=state["last_reason"],
        )
        if isinstance(generated, GenerationFailure):
            # QRY-R013 · QRY-R010 장애면 끝내고, 출력 형식 실패면 다시 생성한다.
            return _after(after_generation_failure(attempt, generated, self._limits))
        return {
            "attempt": attempt,
            "sql": generated.text,
            "step": Generated(attempt, generated.text),
        }

    async def _validate(self, state: _State) -> _State:
        attempt, sql = state["attempt"], state["sql"]
        verdict = judge(
            self._analyzer.analyze(sql),
            allowed_tables=self._allowed,
            row_limit=self._limits.row_limit,
        )
        if isinstance(verdict, Refused):
            return _after(after_rejection(attempt, Stage.VALIDATE, verdict.reason, self._limits))
        # QRY-R005 붙일 행 상한이 없으면 생성 SQL 글 그대로 — 판정한 글과 실행하는 글이 같다.
        if verdict.limit is not None:
            sql = self._analyzer.attach_limit(sql, verdict.limit)
        return {"sql": sql, "step": Validated(sql)}

    async def _execute(self, state: _State) -> _State:
        attempt = state["attempt"]
        # 설계서 2.1 다른 스레드에서 실행한다 — 실행 제한 시간 동안 다른 질문이 멈추지 않게.
        result = await asyncio.to_thread(
            self._database.execute, state["sql"], rows_to_fetch(self._limits.row_limit)
        )
        if isinstance(result, ExecutionFailure):
            reason = execution_failure_reason(result, self._limits)
            return _after(after_rejection(attempt, Stage.EXECUTE, reason, self._limits))
        # QRY-R011 실행 뒤에는 생성기를 부르지 않는다. QRY-R005 · QRY-R014 자르고 값을 정리한다.
        return {"step": Completed(sanitize(cap_rows(result, self._limits.row_limit)))}


def _after(step: Rejected | Failed) -> _State:
    """실패 뒤 규칙이 고른 단계. 다시 생성하면 그 사유가 다음 생성의 직전 실패 사유다."""
    if isinstance(step, Rejected):
        return {"attempt": step.attempt, "last_reason": step.reason, "step": step}
    return {"step": step}


def _route(state: _State) -> str:
    """방금 낸 질의 단계로 다음 노드를 고른다."""
    step = state["step"]
    match step:
        case Generated():
            return _VALIDATE
        case Validated():
            return _EXECUTE
        case Rejected():
            return _GENERATE
        case Completed() | Failed():
            return END
        case _:
            assert_never(step)
