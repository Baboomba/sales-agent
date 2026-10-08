"""SQL 분석기 구현. 바깥(SQLite 방언의 SQL 글)을 SQL 구성으로 제대로 옮기는지 본다.

판정은 규칙 테스트가 본다. 여기서는 옮기기만 본다 (테스트 규칙 7.1).
"""

from __future__ import annotations

import pytest

from app.query.dependency.impl.sqlglot_analyzer import SqlglotAnalyzer
from app.query.model.sql import Qualifier, SqlShape, TableRef
from tests.query.support import assert_reason

ANALYZER = SqlglotAnalyzer()


def plain(table: TableRef, outer_limit: int | None = None) -> SqlShape:
    """표 하나를 읽는 조회문의 SQL 구성."""
    return SqlShape(
        parse_error=None,
        statement_count=1,
        is_query=True,
        forbidden=(),
        tables=(table,),
        cte_names=(),
        outer_limit=outer_limit,
    )


# --- QRY-R002 한 문장 -----------------------------------------------------


def test_qry_r002_two_statements_are_counted_as_two() -> None:
    """QRY-R002 세미콜론으로 이은 `SELECT 1; DELETE FROM orders` 는 문장 둘이다."""
    assert ANALYZER.analyze("SELECT 1; DELETE FROM orders").statement_count == 2


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT store_id FROM stores;",
        "; SELECT store_id FROM stores",
        "SELECT store_id FROM stores;;",
        ";;SELECT store_id FROM stores",
        "SELECT store_id FROM stores; -- done",
        "SELECT store_id FROM stores; /* done */",
    ],
    ids=[
        "trailing",
        "leading",
        "doubled-trailing",
        "doubled-leading",
        "trailing-line-comment",
        "trailing-block-comment",
    ],
)
def test_qry_r002_empty_statements_around_one_statement_do_not_count(sql: str) -> None:
    """QRY-R002 앞뒤에 붙거나 겹친 세미콜론이 만드는 빈 문장은 세지 않는다 — 문장 하나다.

    끝 세미콜론에 주석이 붙어도 같다 (#46).
    """
    assert ANALYZER.analyze(sql) == plain(TableRef("stores"))


@pytest.mark.parametrize(
    "sql",
    ["SELECT 1; DELETE /* zzz */ FROM orders", "SELECT 1; -- zzz\nDELETE FROM orders"],
    ids=["comment-inside-second", "comment-before-second"],
)
def test_qry_r002_statement_after_a_comment_still_counts(sql: str) -> None:
    """QRY-R002 주석이 붙어도 뒤에 오는 진짜 문장은 센다 (#46).

    주석 붙은 끝 세미콜론을 세지 않는 테스트의 짝이다.
    """
    assert ANALYZER.analyze(sql).statement_count == 2


@pytest.mark.parametrize("sql", ["", ";", "  "], ids=["empty", "semicolon", "spaces"])
def test_no_statement_is_counted_as_zero(sql: str) -> None:
    shape = ANALYZER.analyze(sql)
    assert (shape.parse_error, shape.statement_count) == (None, 0)


@pytest.mark.parametrize(
    "sql",
    ["SELECT 'abc", "SELEC store_id FROM stores"],
    ids=["unclosed-quote", "syntax-error"],
)
def test_qry_r002_unparsable_sql_becomes_a_parse_error(sql: str) -> None:
    """QRY-R002 닫히지 않은 따옴표(토큰 오류)와 구문 오류는 예외로 새지 않고 분석 오류가 된다."""
    assert_reason(ANALYZER.analyze(sql).parse_error)


def test_parse_error_is_one_line_without_terminal_codes() -> None:
    """분석 오류의 세부는 한 줄이다.

    sqlglot 의 구문 오류는 여러 줄이고 둘째 줄에 터미널 밑줄 코드(`\\x1b[4m`)가 있다. 세부는
    사유가 되어 화면과 다음 프롬프트에 그대로 가므로, 첫 줄만 옮긴다.
    """
    detail = assert_reason(ANALYZER.analyze("SELEC store_id FROM stores").parse_error)
    assert "\n" not in detail
    assert "\x1b" not in detail


# --- QRY-R003 조회문만 ----------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO orders VALUES (1)",
        "UPDATE orders SET channel = '배달'",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "PRAGMA table_info(orders)",
        "ATTACH DATABASE 'other.db' AS other",
        "BEGIN",
    ],
    ids=["insert", "update", "delete", "drop", "pragma", "attach", "begin"],
)
def test_qry_r003_write_definition_and_admin_statements_are_not_queries_and_forbidden(
    sql: str,
) -> None:
    """QRY-R003 쓰기 · 정의 · 관리 · 트랜잭션 구문은 조회문이 아니고 금지 구문으로 옮긴다."""
    shape = ANALYZER.analyze(sql)
    assert shape.is_query is False
    assert shape.forbidden != ()


def test_qry_r003_delete_inside_cte_is_forbidden() -> None:
    """QRY-R003 조회문 안의 CTE 에 숨긴 DELETE 도 금지 구문으로 옮긴다."""
    shape = ANALYZER.analyze("WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x")
    assert shape.is_query is True
    assert shape.forbidden != ()


@pytest.mark.parametrize(
    "sql",
    [
        "WITH top AS (SELECT store_id FROM orders) SELECT * FROM top",
        "SELECT region FROM stores UNION SELECT category FROM products",
    ],
    ids=["with", "union"],
)
def test_qry_r003_with_and_union_are_queries_without_forbidden(sql: str) -> None:
    """QRY-R003 `WITH ... SELECT` 와 합집합 조회는 조회문이고 금지 구문이 없다."""
    shape = ANALYZER.analyze(sql)
    assert (shape.is_query, shape.forbidden) == (True, ())


# --- QRY-R004 표 참조 -----------------------------------------------------


def test_qry_r004_table_valued_function_becomes_a_function_reference() -> None:
    """QRY-R004 `FROM pragma_database_list()` 는 함수 참조로 옮긴다."""
    shape = ANALYZER.analyze("SELECT * FROM pragma_database_list()")
    assert shape.tables == (TableRef("pragma_database_list", is_function=True),)


def test_qry_r004_qualified_function_keeps_its_qualifier() -> None:
    """QRY-R004 한정자가 붙은 함수 참조는 한정자 종류도 함께 옮긴다."""
    shape = ANALYZER.analyze("SELECT * FROM main.pragma_table_info('orders')")
    assert shape.tables == (
        TableRef("pragma_table_info", Qualifier.DEFAULT_SCHEMA, is_function=True),
    )


@pytest.mark.parametrize(
    ("sql", "qualifier"),
    [
        ("SELECT * FROM orders", Qualifier.NONE),
        ("SELECT * FROM main.orders", Qualifier.DEFAULT_SCHEMA),
        ("SELECT * FROM MAIN.orders", Qualifier.DEFAULT_SCHEMA),
        ("SELECT * FROM aux.orders", Qualifier.OTHER_SCHEMA),
        ("SELECT * FROM temp.orders", Qualifier.OTHER_SCHEMA),
        ("SELECT * FROM main.main.orders", Qualifier.OTHER_SCHEMA),
    ],
    ids=["none", "main", "upper-main", "aux", "temp", "catalog"],
)
def test_qry_r004_qualifier_becomes_its_kind(sql: str, qualifier: Qualifier) -> None:
    """QRY-R004 `main.x` · `MAIN.x` 는 기본 스키마로, 그 밖의 한정자는 다른 스키마로 옮긴다."""
    assert ANALYZER.analyze(sql) == plain(TableRef("orders", qualifier))


def test_tables_anywhere_in_the_statement_are_referenced() -> None:
    """FROM · JOIN · 파생 표 · IN 안의 하위 조회까지 모든 표 참조를 옮긴다."""
    shape = ANALYZER.analyze(
        "SELECT * FROM orders o JOIN stores s ON s.store_id = o.store_id "
        "JOIN (SELECT * FROM products) p ON 1 = 1 "
        "WHERE o.order_id IN (SELECT name FROM sqlite_master)"
    )
    assert set(shape.tables) == {
        TableRef("orders"),
        TableRef("stores"),
        TableRef("products"),
        TableRef("sqlite_master"),
    }


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "WITH top AS (SELECT store_id FROM orders) SELECT * FROM top",
            {TableRef("top"), TableRef("orders")},
        ),
        (
            "WITH t AS (SELECT name FROM sqlite_master) SELECT * FROM t",
            {TableRef("t"), TableRef("sqlite_master")},
        ),
        (
            "WITH sqlite_master AS (SELECT 1) SELECT * FROM sqlite_master",
            {TableRef("sqlite_master")},
        ),
        (
            "WITH sqlite_master AS (SELECT 1) SELECT * FROM main.sqlite_master",
            {TableRef("sqlite_master", Qualifier.DEFAULT_SCHEMA)},
        ),
    ],
    ids=["cte-body", "cte-body-internal", "cte-named-reference", "cte-masked-qualified"],
)
def test_qry_r004_references_are_kept_even_with_ctes(sql: str, expected: set[TableRef]) -> None:
    """QRY-R004 CTE 가 있어도 표 참조를 빼지 않는다 — CTE 이름과 같은 참조도, CTE 몸체 안의 표도.

    CTE 이름인지 가르는 것은 규칙이다. 분석기가 미리 빼면 `main.sqlite_master` 같은 우회가
    규칙에 닿지 않는다 (감사 #17).
    """
    assert set(ANALYZER.analyze(sql).tables) == expected


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT * FROM orders WHERE ('table', 'x') IN sqlite_master",
            {TableRef("orders"), TableRef("sqlite_master")},
        ),
        (
            "SELECT * FROM orders WHERE 1 IN main.sqlite_master",
            {TableRef("orders"), TableRef("sqlite_master", Qualifier.DEFAULT_SCHEMA)},
        ),
        (
            "SELECT * FROM orders WHERE 1 IN aux.sqlite_master",
            {TableRef("orders"), TableRef("sqlite_master", Qualifier.OTHER_SCHEMA)},
        ),
        (
            "SELECT * FROM orders WHERE 1 IN zzz_db.main.sqlite_master",
            {TableRef("orders"), TableRef("sqlite_master", Qualifier.OTHER_SCHEMA)},
        ),
        (
            "SELECT * FROM orders WHERE 1 IN json_each('[1]')",
            {TableRef("orders"), TableRef("json_each", is_function=True)},
        ),
        (
            "SELECT * FROM orders WHERE 1 IN main.pragma_table_list()",
            {
                TableRef("orders"),
                TableRef("pragma_table_list", Qualifier.DEFAULT_SCHEMA, is_function=True),
            },
        ),
        (
            "SELECT * FROM orders WHERE 1 IN aux.zzz_f()",
            {TableRef("orders"), TableRef("zzz_f", Qualifier.OTHER_SCHEMA, is_function=True)},
        ),
        (
            "SELECT * FROM orders WHERE 1 IN zzz_db.main.zzz_f()",
            {TableRef("orders"), TableRef("zzz_f", Qualifier.OTHER_SCHEMA, is_function=True)},
        ),
        ("SELECT * FROM orders WHERE 1 IN (1, 2)", {TableRef("orders")}),
    ],
    ids=[
        "in-table",
        "in-main",
        "in-other-schema",
        "in-catalog",
        "in-function",
        "in-main-function",
        "in-other-schema-function",
        "in-catalog-function",
        "in-values",
    ],
)
def test_qry_r004_in_table_and_in_function_are_references(
    sql: str, expected: set[TableRef]
) -> None:
    """QRY-R004 `IN 표이름` 은 표 참조로, `IN 표 값 함수()` 는 함수 참조로 옮긴다 (#46).

    sqlglot 은 이 자리의 표 이름을 열로, 함수를 일반 함수로 읽는다. 값 목록 `IN (1, 2)` 는
    표 참조가 아니다 — 위 셋의 짝.
    """
    assert set(ANALYZER.analyze(sql).tables) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM sqlite_master, "
        "(WITH sqlite_master AS (SELECT 1) SELECT * FROM sqlite_master)",
        "SELECT * FROM orders WHERE 1 IN (WITH zzz_t AS (SELECT 1) SELECT * FROM zzz_t)",
    ],
    ids=["masking-subquery", "in-subquery"],
)
def test_qry_r004_cte_inside_a_subquery_is_not_a_cte_name(sql: str) -> None:
    """QRY-R004 하위 질의 안의 CTE 이름은 CTE 이름으로 옮기지 않는다 (#46).

    옮기면 바깥의 `sqlite_master` 까지 CTE 로 쳐져 내부 표가 열린다.
    """
    assert ANALYZER.analyze(sql).cte_names == ()


def test_qry_r004_with_inside_a_cte_body_is_not_a_cte_name() -> None:
    """QRY-R004 CTE 몸체 안의 WITH 도 맨 바깥 WITH 가 아니다 — 바깥 CTE 이름만 옮긴다 (#46).

    하위 질의 밖에 있다고 CTE 로 치면, 몸체 안의 `sqlite_master` CTE 가 바깥의 내부 표를 가린다.
    """
    shape = ANALYZER.analyze(
        "WITH zzz_a AS (WITH sqlite_master AS (SELECT 1) SELECT * FROM sqlite_master) "
        "SELECT * FROM zzz_a, sqlite_master"
    )
    assert shape.cte_names == ("zzz_a",)


def test_outer_with_of_a_union_is_collected() -> None:
    """맨 바깥 WITH 는 UNION 에 붙어도 CTE 이름이다 — 위 테스트의 짝."""
    shape = ANALYZER.analyze("WITH zzz_a AS (SELECT 1) SELECT * FROM zzz_a UNION SELECT 2")
    assert shape.cte_names == ("zzz_a",)


def test_every_cte_name_is_collected() -> None:
    shape = ANALYZER.analyze(
        "WITH a AS (SELECT 1), b AS (SELECT 2), c AS (SELECT 3) SELECT * FROM a, b, c"
    )
    assert set(shape.cte_names) == {"a", "b", "c"}


# --- QRY-R005 바깥 행 상한 · 행 상한 붙이기 --------------------------------


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT * FROM orders", None),
        ("SELECT * FROM orders LIMIT 10", 10),
        ("SELECT * FROM orders LIMIT 500", 500),
        ("SELECT * FROM orders LIMIT 0", 0),
        ("SELECT * FROM orders LIMIT -1", -1),
        ("SELECT * FROM orders LIMIT 5, -3", -3),
        ("SELECT * FROM orders LIMIT 1 + 1", None),
        ("SELECT * FROM orders LIMIT '10'", None),
        ("SELECT * FROM orders LIMIT 10.5", None),
        ("SELECT * FROM orders LIMIT -(1 + 1)", None),
    ],
    ids=[
        "none",
        "10",
        "500",
        "0",
        "-1",
        "offset-and-negative",
        "expression",
        "string",
        "float",
        "negative-expression",
    ],
)
def test_qry_r005_outer_limit(sql: str, expected: int | None) -> None:
    """QRY-R005 바깥 행 상한: 없거나 수가 아니면 비어 있고, 음수는 그대로 싣는다."""
    assert ANALYZER.analyze(sql) == plain(TableRef("orders"), outer_limit=expected)


def test_qry_r005_inner_limit_is_not_the_outer_limit() -> None:
    """QRY-R005 하위 조회의 LIMIT 은 바깥 행 상한이 아니다."""
    shape = ANALYZER.analyze("SELECT * FROM (SELECT * FROM orders LIMIT 5) AS s")
    assert shape.outer_limit is None


def test_qry_r005_union_outer_limit_is_read() -> None:
    """QRY-R005 합집합 조회 전체에 붙은 LIMIT 이 바깥 행 상한이다."""
    shape = ANALYZER.analyze(
        "SELECT region FROM stores UNION SELECT category FROM products LIMIT 7"
    )
    assert shape.outer_limit == 7


@pytest.mark.parametrize(
    ("sql", "limit", "expected"),
    [
        ("SELECT store_id FROM stores", 201, "SELECT store_id FROM stores LIMIT 201"),
        ("SELECT store_id FROM stores;", 51, "SELECT store_id FROM stores LIMIT 51"),
        ("SELECT store_id FROM stores LIMIT 500", 201, "SELECT store_id FROM stores LIMIT 201"),
        ("SELECT store_id FROM stores LIMIT -1", 201, "SELECT store_id FROM stores LIMIT 201"),
        (
            "SELECT * FROM (SELECT * FROM stores LIMIT 5000) AS s",
            201,
            "SELECT * FROM (SELECT * FROM stores LIMIT 5000) AS s LIMIT 201",
        ),
        (
            "SELECT region FROM stores UNION SELECT category FROM products",
            51,
            "SELECT region FROM stores UNION SELECT category FROM products LIMIT 51",
        ),
    ],
    ids=["none", "semicolon", "larger", "negative", "inner-kept", "union"],
)
def test_qry_r005_attach_limit_sets_the_outer_limit(sql: str, limit: int, expected: str) -> None:
    """QRY-R005 행 상한을 붙인 SQL — 바깥 LIMIT 을 그 값으로 둔다.

    하위 조회의 LIMIT 은 그대로 둔다.
    """
    assert ANALYZER.attach_limit(sql, limit) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "; SELECT store_id FROM stores",
        "SELECT store_id FROM stores;;",
        ";;SELECT store_id FROM stores",
    ],
    ids=["leading", "doubled-trailing", "doubled-leading"],
)
def test_qry_r005_attach_limit_reads_statements_like_analyze(sql: str) -> None:
    """QRY-R005 행 상한 붙이기는 분석과 같은 방식으로 문장을 읽는다.

    분석은 빈 문장을 세지 않아 이런 SQL 을 한 문장으로 통과시킨다. 붙이기가 다르게 읽으면
    판정을 통과한 SQL 에서 바깥 라이브러리의 예외가 새어 흐름이 끊긴다 (설계서 5.2).
    """
    assert ANALYZER.attach_limit(sql, 201) == "SELECT store_id FROM stores LIMIT 201"


@pytest.mark.parametrize(
    "sql",
    ["SELECT 1; SELECT 2", "DELETE FROM orders"],
    ids=["two-statements", "not-a-query"],
)
def test_attach_limit_refuses_what_judge_would_refuse(sql: str) -> None:
    """판정을 통과하지 못할 SQL 에 행 상한을 붙이라고 하면 거절한다.

    조용히 붙이면 둘째 문장을 버리거나 조회문이 아닌 문장을 고쳐 쓴다. 판정 없이 부른 것은
    버그이므로 예외로 드러낸다 (코드 아키텍처 4절 「예상하지 못한 실패」).
    """
    with pytest.raises(ValueError):
        ANALYZER.attach_limit(sql, 201)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT strftime('%m', ordered_on) AS m FROM orders",
            "SELECT STRFTIME('%m', ordered_on) AS m FROM orders LIMIT 201",
        ),
        ("SELECT * FROM [orders]", 'SELECT * FROM "orders" LIMIT 201'),
    ],
    ids=["sqlite-function", "sqlite-brackets"],
)
def test_qry_r005_attach_limit_reads_and_writes_sqlite(sql: str, expected: str) -> None:
    """QRY-R005 행 상한을 붙인 SQL 은 SQLite 방언으로 읽고 SQLite 방언으로 쓴다.

    다른 방언으로 쓰면 `strftime` 이 SQLite 에 없는 함수로 바뀌어 실행이 깨지고, 다른 방언으로
    읽으면 SQLite 의 `[이름]` 식별자를 읽지 못한다.
    """
    assert ANALYZER.attach_limit(sql, 201) == expected
