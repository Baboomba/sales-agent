"""보조 조회. 가짜 매출 DB 로 무엇을 돌려주는지 본다. 설명을 붙이는 판정은 규칙 테스트가 본다."""

from __future__ import annotations

from dataclasses import replace

from app.query.model.question import Column, Table
from app.query.model.terms import TERMS
from app.query.usecase.lookup import Lookup
from tests.query.fake import ScriptedDatabase

# DB 가 낸 표 목록 — 표 이름 순서와 다르게 둔다. 설명은 비어 있다.
DB_TABLES = (
    Table("zzz_sales", (Column("zzz_c", "REAL"), Column("zzz_a", "INTEGER"))),
    Table("zzz_alpha", (Column("zzz_d", "TEXT"),)),
    Table("zzz_mid", (Column("zzz_e", "TEXT"),)),
)
TERMS_FOR_TEST = replace(
    TERMS,
    table_descriptions={"zzz_sales": "zzz 매출 표", "zzz_absent": "zzz 없는 표"},
    column_descriptions={
        ("zzz_sales", "zzz_a"): "zzz 끝 열",
        ("zzz_mid", "zzz_e"): "zzz 끝 표의 열",
    },
    example_questions=("zzz 둘째 질문", "zzz 첫 질문", "zzz 셋째 질문"),
)


def test_qry_r017_tables_come_from_the_database_in_its_order_with_descriptions() -> None:
    """QRY-R017 표 · 열 조회는 DB 의 표를 DB 의 순서대로, 용어의 설명을 붙여 돌려준다.

    용어에만 있는 표는 더하지 않는다.
    """
    lookup = Lookup(ScriptedDatabase(DB_TABLES, []), TERMS_FOR_TEST)
    assert lookup.tables() == (
        Table(
            "zzz_sales",
            (Column("zzz_c", "REAL", ""), Column("zzz_a", "INTEGER", "zzz 끝 열")),
            "zzz 매출 표",
        ),
        Table("zzz_alpha", (Column("zzz_d", "TEXT", ""),), ""),
        Table("zzz_mid", (Column("zzz_e", "TEXT", "zzz 끝 표의 열"),), ""),
    )


def test_tables_are_read_once_when_the_lookup_is_made() -> None:
    """표 목록은 유스케이스를 만들 때 한 번 읽고, 요청마다 다시 읽지 않는다 (설계서 2.4)."""
    database = ScriptedDatabase(DB_TABLES, [])
    lookup = Lookup(database, TERMS_FOR_TEST)
    assert database.table_reads == 1
    lookup.tables()
    lookup.tables()
    assert database.table_reads == 1


def test_qry_r018_example_questions_are_the_terms_in_their_order() -> None:
    """QRY-R018 예시 질문은 용어의 것을 그 순서대로 돌려준다 (설계서 2.4)."""
    lookup = Lookup(ScriptedDatabase(DB_TABLES, []), TERMS_FOR_TEST)
    assert lookup.example_questions() == ("zzz 둘째 질문", "zzz 첫 질문", "zzz 셋째 질문")
