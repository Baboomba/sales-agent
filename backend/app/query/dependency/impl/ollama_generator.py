"""생성기 구현. 언어 모델에게 프롬프트를 보내고 출력(JSON)을 생성 SQL 로 옮긴다.

바깥(언어 모델의 출력 · 오류)을 생성 SQL · 생성 실패로 옮기기만 한다. 재생성할지 · 어떤 사유로
끝낼지는 규칙이 정한다 (설계서 5.2). 프롬프트의 말투와 형식은 이 구현 안의 일이다.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

import httpx
from ollama import ResponseError

from app.query.model.failure import GenerationFailure, GenerationFailureKind
from app.query.model.question import Question, Table
from app.query.model.sql import GeneratedSql
from app.query.model.terms import Terms

# 프롬프트를 받아 언어 모델의 날 출력을 돌려주는 것. 조립 루트가 Ollama 로 만들어 넘기고
# (`ollama_client.py`), 테스트는 가짜를 넘긴다 — 언어 모델을 부르는 테스트를 쓰지 않는다 (NFR-005).
Complete = Callable[[str], Awaitable[str]]

_CODE_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_ONLY_JSON = '{"sql": "..."} 하나만 출력하세요.'

# 작은 모델은 자주 틀리는 자리(매출 정의 · 날짜 형식 · 별칭 · 출력 형식)를 적어 줘야 맞힌다.
# 문구는 평가로 고른 것이다 — 바꾸면 평가를 다시 돌린다 (docs/eval/README.md).
_INSTRUCTIONS = """너는 SQLite SQL 작성기다. 질문에 답하는 SELECT 문 하나를 만든다.

규칙:
- {revenue}. products.unit_price(정가)로 매출을 계산하지 않는다.
- {order_count}.
- 날짜는 'YYYY-MM-DD' 문자열이다. 기간 조건은 질문에 기간이 있을 때만 넣는다.
- strftime 결과는 문자열이다: '%m' 은 '01'~'12', '%w' 는 '0'(일)~'6'(토). 숫자와 비교하지 않는다.
- 별칭(o, oi, p, s)으로 쓴 표는 반드시 FROM 이나 JOIN 에 넣는다.
- 질문에 없는 조건을 WHERE 에 넣지 않는다.
- 아래 표와 열만 쓴다. 조회만 한다.
- 출력은 JSON 하나뿐이다: {{"sql": "SELECT ..."}}. 설명을 붙이지 않는다."""


class OllamaSqlGenerator:
    def __init__(self, complete: Complete) -> None:
        self._complete = complete

    async def generate(
        self,
        question: Question,
        tables: tuple[Table, ...],
        terms: Terms,
        *,
        last_reason: str | None,
    ) -> GeneratedSql | GenerationFailure:
        prompt = _prompt(question, tables, terms, last_reason)
        try:
            raw = await self._complete(prompt)
        # QRY-R013 모델 서버 장애를 종류별 실패로 옮긴다. 시간 초과는 HTTPError 의 하위라 먼저 본다.
        except httpx.TimeoutException as error:
            return GenerationFailure(GenerationFailureKind.TIMEOUT, str(error))
        except ResponseError as error:
            return GenerationFailure(GenerationFailureKind.ERROR_RESPONSE, error.error)
        except (ConnectionError, httpx.HTTPError) as error:
            return GenerationFailure(GenerationFailureKind.CONNECTION, str(error))
        return _parse(raw)


def _parse(raw: str) -> GeneratedSql | GenerationFailure:
    """QRY-R010 출력 `{"sql": "..."}` 에서 SQL 을 꺼낸다. 작은 모델이 붙이는 코드 펜스는 걷는다."""
    text = _CODE_FENCE.sub("", raw.strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _format_failure("출력이 JSON 이 아닙니다.")
    if not isinstance(payload, dict):
        return _format_failure("출력이 JSON 객체가 아닙니다.")
    sql = payload.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        return _format_failure('출력에 "sql" 값이 없습니다.')
    return GeneratedSql(sql.strip())


def _format_failure(problem: str) -> GenerationFailure:
    # 출력 형식은 이 구현만 아는 바깥이라 고칠 안내도 여기서 짓는다 (설계서 5.2).
    return GenerationFailure(GenerationFailureKind.FORMAT, f"{problem} {_ONLY_JSON}")


def _prompt(
    question: Question, tables: tuple[Table, ...], terms: Terms, last_reason: str | None
) -> str:
    instructions = _INSTRUCTIONS.format(
        revenue=terms.revenue_definition, order_count=terms.order_count_definition
    )
    examples = "\n".join(
        f'질문: {example.question}\n출력: {{"sql": "{example.sql}"}}'
        for example in terms.example_queries
    )
    parts = [instructions, f"표:\n{_describe_tables(tables)}", f"예시:\n{examples}"]
    if last_reason:
        parts.append(f"직전 시도가 실패했다. 사유: {last_reason}\n사유를 고친 SQL 을 다시 만든다.")
    parts.append(f"질문: {question.text}\n출력:")
    return "\n\n".join(parts)


def _describe_tables(tables: tuple[Table, ...]) -> str:
    lines = []
    for table in tables:
        note = f" ({table.description})" if table.description else ""
        columns = ", ".join(
            f"{column.name} {column.type}"
            + (f" — {column.description}" if column.description else "")
            for column in table.columns
        )
        lines.append(f"- {table.name}{note}: {columns}")
    return "\n".join(lines)
