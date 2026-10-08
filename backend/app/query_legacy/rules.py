"""질의 도메인의 규칙. 순수 함수다 — 파일 · 네트워크 · 시각을 쓰지 않는다.

SQL 이 안전한지는 모델이 아니라 이 규칙이 정한다 (docs/architecture.md 3절).
"""

from __future__ import annotations

import json
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

QUESTION_MAX_LENGTH = 300

# 문장 안 어디에 있든 거부하는 구문. 조회문 안에 숨긴 쓰기(CTE 등)까지 잡는다.
FORBIDDEN_NODES: tuple[type[exp.Expr], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Command,
    exp.Transaction,
    exp.Commit,
)

_CODE_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class SqlRejected(Exception):
    """검증에 걸린 SQL. reason 은 다음 생성의 프롬프트에 그대로 붙는다."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class GenerationError(Exception):
    """모델 출력에서 SQL 을 꺼낼 수 없다 (QRY-R010)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def check_question(question: str) -> str | None:
    """QRY-R001 질문이 받을 수 있는 모양인지 본다. 문제가 있으면 사유, 없으면 None."""
    length = len(question.strip())
    if length == 0:
        return "질문이 비어 있습니다."
    if length > QUESTION_MAX_LENGTH:
        return f"질문은 {QUESTION_MAX_LENGTH}자 이하여야 합니다."
    return None


def parse_generation(raw: str) -> str:
    """QRY-R010 모델 출력 {"sql": "..."} 에서 SQL 을 꺼낸다."""
    text = _CODE_FENCE.sub("", raw.strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise GenerationError(
            '출력이 JSON 이 아닙니다. {"sql": "..."} 하나만 출력하세요.'
        ) from error
    if not isinstance(payload, dict):
        raise GenerationError('출력이 JSON 객체가 아닙니다. {"sql": "..."} 하나만 출력하세요.')
    sql = payload.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise GenerationError('출력에 "sql" 값이 없습니다.')
    return sql.strip()


def validate_sql(sql: str, *, allowed_tables: frozenset[str], row_limit: int) -> str:
    """QRY-R002 ~ QRY-R005 실행해도 되는 SQL 인지 판정하고, LIMIT 을 보정해 돌려준다."""
    statement = _single_statement(sql)
    _ensure_read_only(statement)
    _ensure_allowed_tables(statement, allowed_tables)
    return _cap_limit(statement, row_limit)


_MISSING_ALIAS = re.compile(r"no such column: (\w+)\.\w+")


def explain_execution_error(message: str) -> str:
    """QRY-R015 작은 모델이 고칠 곳을 찾도록 실행 오류에 안내를 덧붙인다."""
    match = _MISSING_ALIAS.search(message)
    if not match:
        return message
    alias = match.group(1)
    return (
        f"{message} — 별칭 '{alias}' 의 표가 FROM 이나 JOIN 에 없다. "
        f"'{alias}' 를 쓰려면 그 표를 JOIN 하라."
    )


def sanitize_value(value: object) -> object:
    """QRY-R014 JSON 으로 보낼 수 없는 바이트 값만 바꾼다. 나머지는 손대지 않는다 (NFR-002)."""
    if isinstance(value, bytes | bytearray | memoryview):
        return "<binary>"
    return value


def _single_statement(sql: str) -> exp.Expr:
    """QRY-R002 한 문장만 허용한다."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except SqlglotError as error:
        # ParseError 만 잡으면 TokenError(닫히지 않은 따옴표 등)가 그래프 밖으로 샌다.
        raise SqlRejected(f"SQL 구문 오류입니다: {_first_line(str(error))}") from error
    if len(statements) != 1:
        raise SqlRejected("SQL 은 한 문장이어야 합니다. 세미콜론으로 여러 문장을 잇지 마세요.")
    return statements[0]


def _ensure_read_only(statement: exp.Expr) -> None:
    """QRY-R003 조회문만 허용한다. 문장 안 어디에든 쓰기 · 정의 구문이 있으면 거부한다."""
    if not isinstance(statement, exp.Query):
        raise SqlRejected("조회(SELECT) 문만 실행할 수 있습니다.")
    for node in statement.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlRejected(f"조회문 안에 허용되지 않은 구문이 있습니다: {node.key.upper()}")


def _ensure_allowed_tables(statement: exp.Expr, allowed: frozenset[str]) -> None:
    """QRY-R004 허용된 표만 참조한다 (NFR-008).

    이름만 보면 두 가지가 빠져나간다. sqlglot 은 `FROM f()` 의 표 이름을 빈 문자열로 주고,
    SQLite 는 `main.X` 를 CTE 가 아니라 실제 객체로 푼다. 그래서 셋을 따로 본다.
    """
    real = {name.lower() for name in allowed}
    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    listed = ", ".join(sorted(allowed))
    for table in statement.find_all(exp.Table):
        name = table.name.lower()
        if not name or not isinstance(table.this, exp.Identifier):
            raise SqlRejected(f"FROM 자리에 함수를 쓸 수 없습니다. 쓸 수 있는 표: {listed}")
        if table.args.get("db") or table.args.get("catalog"):
            # 한정자를 붙인 이름은 CTE 가 아니다. 실제 허용 표만 받는다.
            if table.db.lower() != "main" or table.catalog or name not in real:
                raise SqlRejected(f"허용되지 않은 표입니다: {table.sql()}. 쓸 수 있는 표: {listed}")
        elif name not in real | cte_names:
            raise SqlRejected(f"허용되지 않은 표입니다: {table.name}. 쓸 수 있는 표: {listed}")


def _cap_limit(statement: exp.Expr, row_limit: int) -> str:
    """QRY-R005 바깥 LIMIT 이 없거나 상한보다 크면 상한+1 로 둔다.

    한 행 더 가져와야, 결과가 정확히 상한 개수일 때 잘린 것인지 아닌지 안다.
    """
    assert isinstance(statement, exp.Query)
    limit = statement.args.get("limit")
    current = _literal_int(limit.expression) if isinstance(limit, exp.Limit) else None
    if current is not None and current <= row_limit:
        return statement.sql(dialect="sqlite")
    return statement.limit(row_limit + 1, copy=True).sql(dialect="sqlite")


def _literal_int(node: exp.Expr | None) -> int | None:
    if isinstance(node, exp.Literal) and not node.is_string:
        try:
            return int(node.this)
        except ValueError:
            return None
    return None


def _first_line(message: str) -> str:
    return message.strip().splitlines()[0] if message.strip() else message
