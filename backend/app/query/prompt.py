"""SQL 생성 프롬프트를 조립한다. 순수 함수다.

작은 모델을 쓰므로 프롬프트를 짧게 두고, 자주 틀리는 자리(매출 정의 · 날짜 형식 · 출력 형식)를
명시하고, 예시를 붙인다 (docs/architecture.md 3절).
"""

from __future__ import annotations

from app.query.catalog import (
    COLUMN_DESCRIPTIONS,
    FEW_SHOT,
    REVENUE_DEFINITION,
    TABLE_DESCRIPTIONS,
)
from app.query.model import Table

INSTRUCTIONS = f"""너는 SQLite SQL 작성기다. 질문에 답하는 SELECT 문 하나를 만든다.

규칙:
- {REVENUE_DEFINITION}. products.unit_price(정가)로 매출을 계산하지 않는다.
- 날짜는 'YYYY-MM-DD' 문자열이다. 월은 strftime('%m', o.ordered_on) 이나 BETWEEN 으로 거른다.
- 아래 표와 열만 쓴다. 조회만 한다.
- 출력은 JSON 하나뿐이다: {{"sql": "SELECT ..."}}. 설명을 붙이지 않는다."""


def describe_schema(tables: tuple[Table, ...]) -> str:
    lines = []
    for table in tables:
        note = TABLE_DESCRIPTIONS.get(table.name, table.description)
        columns = ", ".join(_describe_column(table.name, c.name, c.type) for c in table.columns)
        lines.append(f"- {table.name} ({note}): {columns}")
    return "\n".join(lines)


def build_prompt(question: str, tables: tuple[Table, ...], *, feedback: str | None) -> str:
    """QRY-R006 질문 · 스키마 · 예시 · 직전 실패 사유로 프롬프트를 만든다."""
    examples = "\n".join(f'질문: {q}\n출력: {{"sql": "{sql}"}}' for q, sql in FEW_SHOT)
    parts = [
        INSTRUCTIONS,
        f"표:\n{describe_schema(tables)}",
        f"예시:\n{examples}",
    ]
    if feedback:
        parts.append(f"직전 시도가 실패했다. 사유: {feedback}\n사유를 고친 SQL 을 다시 만든다.")
    parts.append(f"질문: {question}\n출력:")
    return "\n\n".join(parts)


def _describe_column(table: str, column: str, column_type: str) -> str:
    note = COLUMN_DESCRIPTIONS.get((table, column))
    return f"{column} {column_type}" + (f" — {note}" if note else "")
