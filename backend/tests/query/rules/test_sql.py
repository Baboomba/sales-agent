"""SQL 구성 판정. SQL 글이 아니라 SQL 구성 모델을 넣고 판정을 본다."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from app.query.model.sql import Accepted, Qualifier, Refused, SqlShape, TableRef, Verdict
from app.query.rules.sql import judge
from tests.query.rules.support import assert_reason

ALLOWED = frozenset({"stores", "products", "orders", "order_items"})

# 통과하는 SQL 구성 — `SELECT * FROM orders LIMIT 10`. 테스트마다 한 필드만 바꾼다.
PLAIN = SqlShape(
    parse_error=None,
    statement_count=1,
    is_query=True,
    forbidden=(),
    tables=(TableRef("orders"),),
    cte_names=(),
    outer_limit=10,
)


def judge_with(**changes: Any) -> Verdict:
    return judge(replace(PLAIN, **changes), allowed_tables=ALLOWED, row_limit=200)


def assert_refused(verdict: Verdict) -> str:
    """거부 판정인지 보고 사유를 돌려준다. 통과 판정이거나 사유가 비었으면 실패한다."""
    assert isinstance(verdict, Refused)
    return assert_reason(verdict.reason)


def test_plain_select_passes() -> None:
    """나머지 테스트가 한 필드만 바꿨을 때 거부되는 것이 그 필드 때문임을 보장한다.

    바깥 행 상한 10 은 상한 이하라 그대로 둔다 — 붙일 행 상한이 없다.
    """
    assert judge_with() == Accepted(limit=None)


def test_select_without_tables_passes() -> None:
    """`SELECT 1` 처럼 표를 참조하지 않는 조회는 통과한다 — 볼 표 참조가 없을 뿐이다."""
    assert judge_with(tables=()) == Accepted(limit=None)


# --- QRY-R002 한 문장 -----------------------------------------------------


def test_qry_r002_two_statements_are_refused() -> None:
    """QRY-R002 세미콜론으로 이은 두 번째 문장으로 쓰기를 끼워 넣을 수 없다."""
    assert_refused(judge_with(statement_count=2))


def test_qry_r002_parse_error_is_refused_with_its_detail() -> None:
    """QRY-R002 분석 오류가 있으면 거부하고, 분석기가 준 세부를 사유에 남긴다.

    분석 오류가 있으면 나머지 필드는 의미가 없다. 다른 거부 사유로 세부가 가려지지 않는지 본다.
    """
    verdict = judge_with(
        parse_error="zzz unterminated string at 1:8",
        statement_count=0,
        is_query=False,
        forbidden=("ZZZ_X",),
        tables=(),
        outer_limit=None,
    )
    assert "zzz unterminated string at 1:8" in assert_refused(verdict)


def test_no_statement_is_refused() -> None:
    assert_refused(judge_with(statement_count=0))


# --- QRY-R003 조회문만 ----------------------------------------------------


def test_qry_r003_non_query_is_refused() -> None:
    """QRY-R003 조회문이 아니면 거부한다."""
    assert_refused(judge_with(is_query=False))


def test_qry_r003_forbidden_clauses_are_refused_and_all_named() -> None:
    """QRY-R003 조회문 안에 금지 구문이 있으면 거부하고, 든 구문을 모두 사유에 적는다."""
    reason = assert_refused(judge_with(forbidden=("ZZZ_DELETE", "ZZZ_PRAGMA")))
    assert "ZZZ_DELETE" in reason
    assert "ZZZ_PRAGMA" in reason


# --- QRY-R004 허용된 표만 -------------------------------------------------


@pytest.mark.parametrize(
    "tables",
    [
        (TableRef("sqlite_master"),),
        (TableRef("sqlite_master"), TableRef("orders"), TableRef("stores")),
        (TableRef("orders"), TableRef("sqlite_master"), TableRef("stores")),
        (TableRef("orders"), TableRef("stores"), TableRef("sqlite_master")),
    ],
    ids=["alone", "first", "middle", "last"],
)
def test_qry_r004_table_outside_allowed_is_refused_and_named(
    tables: tuple[TableRef, ...],
) -> None:
    """QRY-R004 허용되지 않은 표는 어느 자리에 있든 거부하고, 그 이름을 사유에 적는다."""
    assert "sqlite_master" in assert_refused(judge_with(tables=tables))


def test_qry_r004_with_query_using_unqualified_cte_name_passes() -> None:
    """QRY-R003 · QRY-R004 `WITH ... SELECT` 는 조회문이다.

    한정자 없이 쓴 CTE 이름은 허용된 표로 친다. 쓰는 CTE 를 CTE 목록의 가운데에 둔다.
    """
    verdict = judge_with(
        cte_names=("zzz_a", "zzz_recent", "zzz_c"),
        tables=(TableRef("zzz_recent"), TableRef("orders")),
    )
    assert isinstance(verdict, Accepted)


@pytest.mark.parametrize(
    "tables",
    [
        (TableRef("sqlite_master"), TableRef("zzz_recent")),
        (TableRef("zzz_recent"), TableRef("sqlite_master")),
    ],
    ids=["before-cte", "after-cte"],
)
def test_qry_r004_cte_does_not_open_other_tables(tables: tuple[TableRef, ...]) -> None:
    """QRY-R004 CTE 가 있어도 CTE 이름이 아닌 비허용 표는 거부한다 — 위 테스트의 짝.

    비허용 표를 CTE 참조의 앞과 뒤에 둔다.
    """
    assert "sqlite_master" in assert_refused(judge_with(cte_names=("zzz_recent",), tables=tables))


@pytest.mark.parametrize(
    "tables",
    [
        (TableRef("orders", is_function=True),),
        (TableRef("orders", is_function=True), TableRef("stores")),
        (TableRef("stores"), TableRef("orders", is_function=True)),
        (TableRef("orders", Qualifier.DEFAULT_SCHEMA, is_function=True),),
    ],
    ids=["alone", "first", "last", "default-schema"],
)
def test_qry_r004_table_valued_function_is_refused(tables: tuple[TableRef, ...]) -> None:
    """QRY-R004 표 값 함수는 언제나 거부한다 — 이름이 허용 표와 같아도, 한정자가 붙어도."""
    assert_refused(judge_with(tables=tables))


def test_qry_r004_function_is_refused_even_with_a_cte_of_the_same_name() -> None:
    """QRY-R004 표 값 함수는 언제나 거부한다 — 같은 이름의 CTE 가 있어도."""
    verdict = judge_with(cte_names=("zzz_f",), tables=(TableRef("zzz_f", is_function=True),))
    assert_refused(verdict)


def test_qry_r004_qualified_name_masked_by_cte_is_refused() -> None:
    """QRY-R004 CTE 이름으로 가린 `main.sqlite_master` 는 거부한다.

    기본 스키마를 붙인 이름은 CTE 가 아니다.
    """
    verdict = judge_with(
        cte_names=("sqlite_master",),
        tables=(TableRef("sqlite_master", Qualifier.DEFAULT_SCHEMA),),
    )
    assert "sqlite_master" in assert_refused(verdict)


def test_qry_r004_default_schema_allowed_table_passes() -> None:
    """QRY-R004 `main.orders` 처럼 기본 스키마를 붙여도 실제 허용 표면 받는다."""
    verdict = judge_with(tables=(TableRef("orders", Qualifier.DEFAULT_SCHEMA),))
    assert isinstance(verdict, Accepted)


def test_qry_r004_other_schema_table_is_refused_even_if_its_name_is_allowed() -> None:
    """QRY-R004 다른 스키마를 붙인 이름은 거부한다 — 이름이 허용 표와 같아도."""
    verdict = judge_with(tables=(TableRef("orders", Qualifier.OTHER_SCHEMA),))
    assert_refused(verdict)


@pytest.mark.parametrize(
    ("cte_names", "tables"),
    [
        ((), (TableRef("orders", Qualifier.DEFAULT_SCHEMA), TableRef("sqlite_master"))),
        (
            (),
            (TableRef("stores"), TableRef("orders", Qualifier.DEFAULT_SCHEMA), TableRef("zzz_x")),
        ),
        (
            ("sqlite_master",),
            (TableRef("orders"), TableRef("sqlite_master", Qualifier.DEFAULT_SCHEMA)),
        ),
        ((), (TableRef("orders"), TableRef("orders", Qualifier.OTHER_SCHEMA), TableRef("stores"))),
        ((), (TableRef("orders"), TableRef("stores"), TableRef("orders", Qualifier.OTHER_SCHEMA))),
    ],
    ids=[
        "after-default-schema",
        "after-default-schema-middle",
        "masked-last",
        "other-schema-middle",
        "other-schema-last",
    ],
)
def test_qry_r004_qualified_references_are_judged_in_any_position(
    cte_names: tuple[str, ...], tables: tuple[TableRef, ...]
) -> None:
    """QRY-R004 한정자가 붙은 참조도 어느 자리에 있든 판정한다.

    기본 스키마의 허용 표 뒤에 온 비허용 표, 가운데 · 끝에 온 다른 스키마 참조를 놓치지 않는다.
    """
    assert_refused(judge_with(cte_names=cte_names, tables=tables))


@pytest.mark.parametrize(("table", "accepted"), [("zzz_sales", True), ("orders", False)])
def test_qry_r004_allowed_tables_come_from_the_argument(table: str, accepted: bool) -> None:
    """QRY-R004 허용된 표는 넘겨받은 목록이다 — 고정된 표 이름이 아니다."""
    verdict = judge(
        replace(PLAIN, tables=(TableRef(table),)),
        allowed_tables=frozenset({"zzz_sales"}),
        row_limit=200,
    )
    assert isinstance(verdict, Accepted) is accepted


@pytest.mark.parametrize(
    ("allowed", "ctes", "ref"),
    [
        (frozenset({"orders"}), (), TableRef("ORDERS")),
        (frozenset({"Orders"}), (), TableRef("orders")),
        (frozenset({"Orders"}), (), TableRef("ORDERS", Qualifier.DEFAULT_SCHEMA)),
        (frozenset({"orders"}), ("ZZZ_Recent",), TableRef("zzz_recent")),
        (frozenset({"orders"}), ("zzz_recent",), TableRef("ZZZ_RECENT")),
    ],
    ids=[
        "upper-reference",
        "upper-allowed",
        "default-schema",
        "upper-cte-name",
        "upper-cte-reference",
    ],
)
def test_qry_r004_names_are_compared_case_insensitively(
    allowed: frozenset[str], ctes: tuple[str, ...], ref: TableRef
) -> None:
    """QRY-R004 표 · CTE 이름은 대소문자를 가리지 않는다 — 정의 쪽과 참조 쪽 모두."""
    verdict = judge(
        replace(PLAIN, cte_names=ctes, tables=(ref,)), allowed_tables=allowed, row_limit=200
    )
    assert isinstance(verdict, Accepted)


@pytest.mark.parametrize(
    "ref",
    [
        TableRef("sqlite_master"),
        TableRef("zzz_func", is_function=True),
        TableRef("zzz_other", Qualifier.OTHER_SCHEMA),
    ],
    ids=["disallowed", "function", "other-schema"],
)
def test_table_refusal_lists_every_usable_table(ref: TableRef) -> None:
    """표 참조로 거부할 때는 쓸 수 있는 표를 모두 알려 준다 — 다음 생성이 고칠 곳을 찾게.

    참조 이름은 쓸 수 있는 표 이름과 겹치지 않게 둔다 — 사유의 표 이름이 목록에서만 나오게.
    """
    verdict = judge(
        replace(PLAIN, tables=(ref,)),
        allowed_tables=frozenset({"zzz_sales", "zzz_stock"}),
        row_limit=200,
    )
    reason = assert_refused(verdict)
    assert "zzz_sales" in reason
    assert "zzz_stock" in reason


# --- 통과 판정이 싣는 행 상한 ---------------------------------------------


def test_accepted_verdict_carries_the_row_limit_to_attach() -> None:
    """판정이 SQL 구성의 바깥 행 상한으로 정한 값을 싣는지만 본다.

    붙일 행 상한의 판단 자체는 QRY-R005 테스트가 본다. 그대로 두는 경우는 맨 위 기준선이 본다.
    """
    verdict = judge(replace(PLAIN, outer_limit=None), allowed_tables=ALLOWED, row_limit=50)
    assert verdict == Accepted(limit=51)
