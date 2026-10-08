"""질의 Agent 그래프. generate → validate → execute 와 재생성 루프 (docs/design/query.md 2절).

포트만 안다. 어떤 모델 서버 · 어떤 DB 인지는 조립 루트(app/main.py)가 정한다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.query.model import (
    Done,
    Event,
    Failed,
    Generated,
    QueryState,
    Rejected,
    Stage,
    Validated,
)
from app.query.ports import ExecutionError, GeneratorUnavailable, SalesDatabase, SqlGenerator
from app.query.prompt import build_prompt
from app.query.rules import (
    GenerationError,
    SqlRejected,
    explain_execution_error,
    parse_generation,
    sanitize_value,
    validate_sql,
)

UNAVAILABLE_REASON = "모델 서버에 연결할 수 없습니다. Ollama 가 떠 있는지 확인하세요."
UNEXPECTED_REASON = "처리 중 예상하지 못한 오류가 났습니다. 다시 시도해 주세요."

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentSettings:
    max_attempts: int  # QRY-R006 생성 최대 횟수 (처음 포함)
    row_limit: int  # QRY-R005 행 상한


class SqlAgent:
    def __init__(
        self, generator: SqlGenerator, database: SalesDatabase, settings: AgentSettings
    ) -> None:
        self._generator = generator
        self._database = database
        self._settings = settings
        self._tables = database.schema()
        self._allowed = frozenset(t.name for t in self._tables)
        self._graph = self._build()

    async def stream(self, question: str) -> AsyncIterator[Event]:
        """QRY-R012 단계가 끝날 때마다 이벤트를 하나씩 낸다. 마지막은 done 이나 failed 다."""
        initial: QueryState = {"question": question, "attempt": 0, "outcome": "running"}
        try:
            async for chunk in self._graph.astream(initial, stream_mode="updates"):
                for node, update in chunk.items():
                    yield _to_event(node, update)
        except Exception:
            # 안전망. 예상한 실패는 노드가 상태로 돌려준다. 여기 오는 것은 버그이므로 남긴다.
            logger.exception("질의 처리 중 예상하지 못한 오류")
            yield Failed(reason=UNEXPECTED_REASON)

    # --- 그래프 -----------------------------------------------------------

    def _build(self) -> Any:
        graph = StateGraph(QueryState)
        graph.add_node("generate", self._generate)
        graph.add_node("validate", self._validate)
        graph.add_node("execute", self._execute)
        graph.add_edge(START, "generate")
        graph.add_conditional_edges(
            "generate", _route_to("validate"), ["validate", "generate", END]
        )
        graph.add_conditional_edges("validate", _route_to("execute"), ["execute", "generate", END])
        graph.add_conditional_edges("execute", _route_to(END), ["generate", END])
        return graph.compile()

    async def _generate(self, state: QueryState) -> QueryState:
        attempt = state.get("attempt", 0) + 1
        prompt = build_prompt(state["question"], self._tables, feedback=state.get("feedback"))
        try:
            raw = await self._generator.generate(prompt)
        except GeneratorUnavailable as error:
            # QRY-R013 다시 해도 안 되는 실패. 재생성 횟수를 깎지 않고 바로 끝낸다.
            reason = f"{UNAVAILABLE_REASON} ({error})"
            return {"attempt": attempt, "outcome": "failed", "reason": reason}
        try:
            sql = parse_generation(raw)
        except GenerationError as error:
            return self._reject(attempt, "generate", error.reason)
        return {"attempt": attempt, "stage": "generate", "sql": sql, "feedback": None}

    async def _validate(self, state: QueryState) -> QueryState:
        try:
            validated = validate_sql(
                state["sql"], allowed_tables=self._allowed, row_limit=self._settings.row_limit
            )
        except SqlRejected as error:
            return self._reject(state["attempt"], "validate", error.reason)
        return {"stage": "validate", "sql": validated.sql, "capped": validated.capped}

    async def _execute(self, state: QueryState) -> QueryState:
        try:
            result = await asyncio.to_thread(self._database.execute, state["sql"])
        except ExecutionError as error:
            reason = f"실행 오류: {explain_execution_error(str(error))}"
            return self._reject(state["attempt"], "execute", reason)
        # QRY-R011 실행 뒤에는 모델을 부르지 않는다. 값은 DB 가 낸 그대로다.
        rows = tuple(tuple(sanitize_value(v) for v in row) for row in result.rows)
        truncated = state.get("capped", False) and len(rows) >= self._settings.row_limit
        return {
            "stage": "execute",
            "columns": result.columns,
            "rows": rows,
            "truncated": truncated,
            "outcome": "done",
        }

    def _reject(self, attempt: int, stage: Stage, reason: str) -> QueryState:
        """QRY-R006 · QRY-R007 한도 안이면 사유를 남겨 재생성으로, 넘으면 실패로 끝낸다."""
        if attempt >= self._settings.max_attempts:
            return {
                "attempt": attempt,
                "stage": stage,
                "feedback": reason,
                "outcome": "failed",
                "reason": (
                    f"{attempt}번 시도했지만 실행할 수 있는 SQL 을 만들지 못했습니다. "
                    f"마지막 사유: {reason}"
                ),
            }
        return {"attempt": attempt, "stage": stage, "feedback": reason}


def _route_to(next_node: str) -> Callable[[QueryState], str]:
    def route(state: QueryState) -> str:
        if state.get("outcome") in ("failed", "done"):
            return END
        if state.get("feedback"):
            return "generate"
        return next_node

    return route


def _to_event(node: str, update: QueryState) -> Event:
    """그래프 단계의 갱신을 화면이 받을 이벤트로 옮긴다 (docs/design/query.md 2.4)."""
    if update.get("outcome") == "failed":
        return Failed(reason=update["reason"])
    if feedback := update.get("feedback"):
        return Rejected(attempt=update["attempt"], stage=update["stage"], reason=feedback)
    if node == "generate":
        return Generated(attempt=update["attempt"], sql=update["sql"])
    if node == "validate":
        return Validated(sql=update["sql"])
    return Done(columns=update["columns"], rows=update["rows"], truncated=update["truncated"])
