"""SQL 분석기 구현. SQLite 방언을 sqlglot 으로 읽는다.

바깥(sqlglot 의 노드 · 예외)을 SQL 구성으로 옮기기만 한다. 판정은 규칙이 한다 (설계서 5.2).
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.query.model.sql import Qualifier, SqlShape, TableRef

_DIALECT = "sqlite"
_DEFAULT_SCHEMA = "main"

# 쓰기 · 정의 · 관리 · 트랜잭션 구문 (설계서 3절 QRY-R003). 어느 노드가 그것인지는 sqlglot 을 아는
# 이 자리가 옮긴다 (코드 아키텍처 2.1). sqlglot 이 모르는 문장(VACUUM 등)은 Command 로 온다.
_FORBIDDEN_NODES: tuple[type[exp.Expr], ...] = (
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
    exp.Rollback,
)


class SqlglotAnalyzer:
    def analyze(self, sql: str) -> SqlShape:
        try:
            statements = _statements(sql)
        except SqlglotError as error:
            # ParseError 만 잡으면 TokenError(닫히지 않은 따옴표 등)가 새어 흐름이 끊긴다 (#21).
            return _shape_without_statement(parse_error=_first_line(str(error)), statement_count=0)
        if len(statements) != 1:
            # 규칙이 문장 수로 먼저 거부하므로 나머지 필드는 채우지 않는다.
            return _shape_without_statement(parse_error=None, statement_count=len(statements))
        statement = statements[0]
        return SqlShape(
            parse_error=None,
            statement_count=1,
            is_query=isinstance(statement, exp.Query),
            forbidden=tuple(
                node.key.upper() for node in statement.walk() if isinstance(node, _FORBIDDEN_NODES)
            ),
            # CTE 이름과 같은 참조 · CTE 몸체 안의 표도 모두 담는다. CTE 인지 가르는 것은 규칙이다.
            tables=(
                *(_table_ref(table) for table in statement.find_all(exp.Table)),
                *(ref for node in statement.find_all(exp.In) if (ref := _in_ref(node))),
            ),
            cte_names=_outer_cte_names(statement),
            outer_limit=_outer_limit(statement),
        )

    def attach_limit(self, sql: str, limit: int) -> str:
        statements = _statements(sql)
        if len(statements) != 1 or not isinstance(statements[0], exp.Query):
            raise ValueError("행 상한은 판정을 통과한 조회문 한 문장에만 붙인다.")
        return statements[0].limit(limit, copy=True).sql(dialect=_DIALECT)


def _statements(sql: str) -> list[exp.Expr]:
    """SQL 글을 문장으로 읽는다. 세미콜론이 만드는 빈 문장은 거른다.

    분석과 행 상한 붙이기가 같은 읽기를 써야, 판정을 통과한 SQL 을 붙이기가 다르게 읽지 않는다.
    """
    # 끝 세미콜론에 주석이 붙으면 sqlglot 이 주석만 든 Semicolon 노드를 따로 낸다 (#46).
    return [
        statement
        for statement in sqlglot.parse(sql, read=_DIALECT)
        if statement is not None and not isinstance(statement, exp.Semicolon)
    ]


def _shape_without_statement(*, parse_error: str | None, statement_count: int) -> SqlShape:
    """분석 오류가 났거나 문장이 하나가 아닐 때의 SQL 구성."""
    return SqlShape(
        parse_error=parse_error,
        statement_count=statement_count,
        is_query=False,
        forbidden=(),
        tables=(),
        cte_names=(),
        outer_limit=None,
    )


def _table_ref(table: exp.Table) -> TableRef:
    # sqlglot 은 `FROM f()` 를 이름이 빈 표로 주고 함수를 this 에 둔다(generate_series 처럼 함수
    # 이름마저 비는 것도 있다). 그래서 이름이 아니라 this 가 식별자인지로 가른다.
    if not isinstance(table.this, exp.Identifier):
        return TableRef(name=table.this.name, qualifier=_qualifier(table), is_function=True)
    return TableRef(name=table.name, qualifier=_qualifier(table))


def _in_ref(node: exp.In) -> TableRef | None:
    """`IN 표이름` · `IN 표 값 함수()` 의 참조 (#46). 값 목록 · 하위 조회는 None.

    sqlglot 은 이 자리의 표 이름을 열(`main.x` 면 표 자리에 `main` 이 든 열)로, 함수를 일반
    함수로, 한정자가 붙은 함수(`main.f()`)를 Dot 으로 읽는다. 하위 조회 안의 표는 Table 노드로
    따로 잡힌다.
    """
    field = node.args.get("field")
    if isinstance(field, exp.Column):
        qualifier = _schema_qualifier(field.table, has_catalog=field.args.get("db") is not None)
        return TableRef(name=field.name, qualifier=qualifier)
    if isinstance(field, exp.Func):
        return TableRef(name=field.name, is_function=True)
    if isinstance(field, exp.Dot) and isinstance(field.expression, exp.Func):
        schema = field.this
        if isinstance(schema, exp.Identifier):
            qualifier = _schema_qualifier(schema.name, has_catalog=False)
        else:
            qualifier = Qualifier.OTHER_SCHEMA  # `카탈로그.스키마.f()`
        return TableRef(name=field.expression.name, qualifier=qualifier, is_function=True)
    return None


def _outer_cte_names(statement: exp.Expr) -> tuple[str, ...]:
    """맨 바깥 WITH 의 CTE 이름 (설계서 5.1).

    하위 질의 안의 CTE 는 바깥 이름을 가리지 못한다 (#46).
    """
    with_ = statement.args.get("with_")
    if not isinstance(with_, exp.With):
        return ()
    return tuple(cte.alias_or_name for cte in with_.expressions)


def _qualifier(table: exp.Table) -> Qualifier:
    return _schema_qualifier(table.db, has_catalog=bool(table.catalog))


def _schema_qualifier(schema: str, *, has_catalog: bool) -> Qualifier:
    """한정자를 한정자 종류로 옮긴다. 어느 이름이 기본 스키마인지는 SQLite 방언이다."""
    if has_catalog:
        return Qualifier.OTHER_SCHEMA
    if not schema:
        return Qualifier.NONE
    if schema.lower() == _DEFAULT_SCHEMA:
        return Qualifier.DEFAULT_SCHEMA
    return Qualifier.OTHER_SCHEMA


def _outer_limit(statement: exp.Expr) -> int | None:
    """바깥 행 상한. 없거나 수가 아니면 None, 음수는 그대로 (설계서 5.1)."""
    limit = statement.args.get("limit")
    if not isinstance(limit, exp.Limit):
        return None
    return _integer(limit.expression)


def _integer(node: exp.Expr | None) -> int | None:
    # sqlglot 은 `-1` 을 Neg(1) 로 준다.
    if isinstance(node, exp.Neg):
        inner = _integer(node.this)
        return None if inner is None else -inner
    if isinstance(node, exp.Literal) and not node.is_string:
        try:
            return int(node.this)
        except ValueError:
            return None
    return None


def _first_line(message: str) -> str:
    # 둘째 줄부터는 터미널 밑줄 코드가 섞인 위치 표시다. 사유로는 첫 줄만 쓴다.
    return message.strip().split("\n", 1)[0]
