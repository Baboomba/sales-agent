"""SQL 검증 · 모델 출력 해석 · 값 정리 규칙. 순수 함수라 모델도 DB 도 없다."""

from __future__ import annotations

import pytest

from app.query.rules import (
    GenerationError,
    SqlRejected,
    check_question,
    explain_execution_error,
    parse_generation,
    sanitize_value,
    validate_sql,
)

ALLOWED = frozenset({"stores", "products", "orders", "order_items"})


def validate(sql: str, row_limit: int = 200) -> str:
    return validate_sql(sql, allowed_tables=ALLOWED, row_limit=row_limit).sql


def reason_of(sql: str) -> str:
    with pytest.raises(SqlRejected) as info:
        validate(sql)
    return info.value.reason


# --- QRY-R001 질문 길이 ---------------------------------------------------


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_qry_r001_empty_question_is_rejected(question: str) -> None:
    """QRY-R001 공백뿐인 질문은 받지 않는다."""
    assert check_question(question) is not None


def test_qry_r001_question_length_boundary() -> None:
    """QRY-R001 300자는 받고 301자는 받지 않는다."""
    assert check_question("가" * 300) is None
    assert check_question("가" * 301) is not None


# --- QRY-R002 한 문장 -----------------------------------------------------


def test_qry_r002_multiple_statements_are_rejected() -> None:
    """QRY-R002 세미콜론으로 이은 두 번째 문장으로 쓰기를 끼워 넣을 수 없다."""
    assert "한 문장" in reason_of("SELECT 1; DELETE FROM orders")


def test_qry_r002_trailing_semicolon_is_one_statement() -> None:
    """QRY-R002 끝에 붙은 세미콜론 하나는 한 문장이다."""
    assert validate("SELECT store_id FROM stores;").startswith("SELECT")


# --- QRY-R003 조회문만 ----------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO stores (name) VALUES ('x')",
        "UPDATE orders SET channel = '배달'",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "CREATE TABLE t (a INT)",
        "PRAGMA table_info(orders)",
        "ATTACH DATABASE 'x.db' AS x",
    ],
)
def test_qry_r003_write_and_definition_statements_are_rejected(sql: str) -> None:
    """QRY-R003 쓰기 · 정의 · 관리 구문은 거부한다."""
    with pytest.raises(SqlRejected):
        validate(sql)


def test_qry_r003_write_inside_cte_is_rejected() -> None:
    """QRY-R003 CTE 안에 숨긴 쓰기도 거부한다."""
    with pytest.raises(SqlRejected):
        validate("WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x")


def test_qry_r003_with_select_is_allowed() -> None:
    """QRY-R003 WITH ... SELECT 조회는 허용한다."""
    sql = "WITH s AS (SELECT store_id FROM stores) SELECT store_id FROM s"
    assert "SELECT" in validate(sql)


def test_qry_r003_syntax_error_is_rejected_with_reason() -> None:
    """QRY-R003 구문이 깨진 SQL 은 사유를 붙여 거부한다."""
    assert "구문" in reason_of("SELEC store_id FROM stores")


# --- QRY-R004 허용된 표만 -------------------------------------------------


def test_qry_r004_internal_table_is_rejected() -> None:
    """QRY-R004 sqlite_master 같은 내부 표는 거부한다."""
    assert "sqlite_master" in reason_of("SELECT name FROM sqlite_master")


def test_qry_r004_cte_name_counts_as_allowed() -> None:
    """QRY-R004 CTE 로 만든 이름은 허용된 표로 친다."""
    sql = "WITH top AS (SELECT store_id FROM orders) SELECT * FROM top"
    assert "top" in validate(sql)


def test_qry_r004_table_names_are_case_insensitive() -> None:
    """QRY-R004 표 이름의 대소문자는 가리지 않는다."""
    assert "FROM" in validate("SELECT * FROM Stores")


# --- QRY-R005 LIMIT 보정 --------------------------------------------------


def test_qry_r005_missing_limit_is_added() -> None:
    """QRY-R005 바깥 LIMIT 이 없으면 상한을 붙이고, 붙였다고 알린다."""
    result = validate_sql("SELECT * FROM stores", allowed_tables=ALLOWED, row_limit=200)
    assert result.sql.endswith("LIMIT 200")
    assert result.capped is True


def test_qry_r005_large_limit_is_reduced() -> None:
    """QRY-R005 상한보다 큰 LIMIT 은 상한으로 줄인다."""
    result = validate_sql("SELECT * FROM stores LIMIT 500", allowed_tables=ALLOWED, row_limit=200)
    assert result.sql.endswith("LIMIT 200")
    assert result.capped is True


def test_qry_r005_small_limit_is_kept() -> None:
    """QRY-R005 상한보다 작은 LIMIT 은 그대로 둔다."""
    result = validate_sql("SELECT * FROM stores LIMIT 10", allowed_tables=ALLOWED, row_limit=200)
    assert result.sql.endswith("LIMIT 10")
    assert result.capped is False


def test_qry_r005_inner_limit_does_not_count_as_outer() -> None:
    """QRY-R005 서브쿼리 안의 LIMIT 은 바깥 LIMIT 이 아니다."""
    sql = "SELECT * FROM (SELECT * FROM stores LIMIT 5000) AS s"
    assert validate(sql).endswith("LIMIT 200")


# --- QRY-R010 모델 출력 해석 ----------------------------------------------


def test_qry_r010_json_sql_is_extracted() -> None:
    """QRY-R010 {"sql": ...} 에서 SQL 을 꺼낸다."""
    assert parse_generation('{"sql": "SELECT 1"}') == "SELECT 1"


def test_qry_r010_code_fence_is_tolerated() -> None:
    """QRY-R010 작은 모델이 자주 붙이는 코드 펜스를 걷어낸다."""
    raw = '```json\n{"sql": "SELECT 1"}\n```'
    assert parse_generation(raw) == "SELECT 1"


@pytest.mark.parametrize("raw", ["SELECT 1", '{"query": "SELECT 1"}', '{"sql": "  "}', "[]"])
def test_qry_r010_invalid_output_is_generation_error(raw: str) -> None:
    """QRY-R010 JSON 이 아니거나 sql 이 비면 생성 실패다."""
    with pytest.raises(GenerationError):
        parse_generation(raw)


# --- QRY-R014 값 정리 -----------------------------------------------------


def test_qry_r014_bytes_become_placeholder() -> None:
    """QRY-R014 바이트 값은 그대로 보내지 않는다."""
    assert sanitize_value(b"\x00\x01") == "<binary>"


@pytest.mark.parametrize("value", [None, 1, 2.5, "강남점"])
def test_qry_r014_plain_values_are_kept(value: object) -> None:
    """QRY-R014 바이트가 아닌 값은 바꾸지 않는다 (NFR-002)."""
    assert sanitize_value(value) == value


# --- QRY-R015 실행 오류 안내 -----------------------------------------------


def test_qry_r015_missing_alias_gets_join_hint() -> None:
    """QRY-R015 별칭 없이 쓴 열이면 그 별칭의 표를 JOIN 했는지 확인하라고 덧붙인다."""
    hint = explain_execution_error("no such column: o.ordered_on")
    assert hint.startswith("no such column: o.ordered_on")
    assert "'o'" in hint
    assert "JOIN" in hint


@pytest.mark.parametrize("message", ["no such column: nope", 'near "FORM": syntax error'])
def test_qry_r015_other_errors_are_kept_as_is(message: str) -> None:
    """QRY-R015 별칭 열 오류가 아니면 손대지 않는다."""
    assert explain_execution_error(message) == message
