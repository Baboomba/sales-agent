"""용어."""

from __future__ import annotations

from dataclasses import replace

from app.query.model.question import Column, Table
from app.query.model.terms import TERMS, ExampleQuery
from app.query.rules.terms import describe_tables, overlapping_examples

# DB 가 낸 표 목록 — 표도 열도 이름 순서와 다르게 둔다. 설명은 비어 있다.
FROM_DATABASE = (
    Table(
        "zzz_sales",
        (Column("zzz_c", "REAL"), Column("zzz_a", "INTEGER"), Column("zzz_b", "TEXT")),
    ),
    Table("zzz_alpha", (Column("zzz_d", "TEXT"),)),
    Table("zzz_mid", (Column("zzz_e", "TEXT"),)),
)


def test_qry_r017_descriptions_come_from_terms_in_database_order() -> None:
    """QRY-R017 표 · 열은 DB 의 순서 그대로, 설명은 용어에서 붙이고 없으면 빈 문자열이다.

    용어에만 있는 표 · 열은 더하지 않는다. 열 설명은 (표, 열) 짝으로 찾는다 — 다른 표의 같은
    열 이름에 붙은 설명은 붙지 않는다.
    """
    terms = replace(
        TERMS,
        table_descriptions={
            "zzz_sales": "zzz 매출 표",
            "zzz_mid": "zzz 가운데 표",
            "zzz_absent": "zzz 없는 표",
        },
        column_descriptions={
            ("zzz_sales", "zzz_c"): "zzz 첫 열",
            ("zzz_sales", "zzz_b"): "zzz 끝 열",
            ("zzz_mid", "zzz_e"): "zzz 가운데 표의 열",
            ("zzz_mid", "zzz_a"): "zzz 다른 표의 같은 이름",
            ("zzz_alpha", "zzz_absent_col"): "zzz 없는 열",
        },
    )
    assert describe_tables(FROM_DATABASE, terms) == (
        Table(
            "zzz_sales",
            (
                Column("zzz_c", "REAL", "zzz 첫 열"),
                Column("zzz_a", "INTEGER", ""),
                Column("zzz_b", "TEXT", "zzz 끝 열"),
            ),
            "zzz 매출 표",
        ),
        Table("zzz_alpha", (Column("zzz_d", "TEXT", ""),), ""),
        Table("zzz_mid", (Column("zzz_e", "TEXT", "zzz 가운데 표의 열"),), "zzz 가운데 표"),
    )


def test_qry_r018_terms_have_no_overlapping_example_questions() -> None:
    """QRY-R018 지금 용어의 예시 질문은 예시 질의의 질문과 겹치지 않는다."""
    assert overlapping_examples(TERMS) == ()


def test_qry_r018_overlap_is_found() -> None:
    """QRY-R018 겹치는 예시 질문을 모두 찾는다.

    위 테스트가 아무것도 못 찾는 구현에서 통과하지 않게 하는 짝이다.
    두 예시 질의가 모두 겹치고, 겹치는 예시 질문은 처음과 끝에, 겹치지 않는 것은 가운데에 둔다.
    예시 질의는 예시 질문과 반대 순서로 둔다 — 결과는 예시 질문의 순서를 따른다.
    """
    terms = replace(
        TERMS,
        example_queries=(
            ExampleQuery("zzz 둘째 질문", "SELECT 2"),
            ExampleQuery("zzz 첫 질문", "SELECT 1"),
        ),
        example_questions=("zzz 첫 질문", "다른 질문", "zzz 둘째 질문"),
    )
    assert overlapping_examples(terms) == ("zzz 첫 질문", "zzz 둘째 질문")
