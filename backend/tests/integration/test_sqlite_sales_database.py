"""매출 DB 구현. 실제 SQLite 파일에 닿아야 보이는 것을 본다 (테스트 규칙 7.1).

실행 실패를 어떻게 안내할지는 규칙 테스트가 본다. 여기서는 바깥(SQLite)을 모델 · 실패로
옮기는 것과 읽기 전용 · 제한 시간 · 가져올 행 수만 본다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from app.query.dependency.impl.sqlite_sales_database import SqliteSalesDatabase
from app.query.model.failure import ExecutionFailure, ExecutionFailureKind
from app.query.model.question import Column, Table
from app.query.model.run import QueryResult

pytestmark = pytest.mark.integration

ENDLESS = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """표 둘을 이름 순서와 다르게 만든다.

    내부 표(AUTOINCREMENT 가 만드는 `sqlite_sequence`)와 뷰도 둔다.
    """
    path = tmp_path / "sales.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE stores (store_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, region TEXT);
        CREATE TABLE ab_items (item_id INTEGER, price REAL);
        CREATE VIEW store_names AS SELECT name FROM stores;
        INSERT INTO stores (name, region) VALUES
            ('강남점', '서울'), ('해운대점', '부산'), ('판교점', '경기'),
            ('동성로점', '대구'), ('둔산점', '대전');
        """
    )
    conn.commit()
    conn.close()
    return path


def database(path: Path, timeout_seconds: float = 5) -> SqliteSalesDatabase:
    return SqliteSalesDatabase(path, timeout_seconds=timeout_seconds)


# --- QRY-R017 표 목록 -----------------------------------------------------


def test_qry_r017_tables_are_regular_tables_in_database_order(db_path: Path) -> None:
    """QRY-R017 일반 표와 그 열을 DB 순서대로 낸다. 내부 표 · 뷰는 내지 않고, 설명은 비어 있다."""
    assert database(db_path).tables() == (
        Table(
            "stores",
            (Column("store_id", "INTEGER"), Column("name", "TEXT"), Column("region", "TEXT")),
        ),
        Table("ab_items", (Column("item_id", "INTEGER"), Column("price", "REAL"))),
    )


# --- 실행 결과 · QRY-R005 가져올 행 수 ------------------------------------


def test_execute_returns_columns_and_rows(db_path: Path) -> None:
    result = database(db_path).execute(
        "SELECT name, region FROM stores WHERE store_id <= 2 ORDER BY store_id", fetch=10
    )
    assert result == QueryResult(("name", "region"), (("강남점", "서울"), ("해운대점", "부산")))


def test_empty_result_keeps_its_columns(db_path: Path) -> None:
    result = database(db_path).execute("SELECT name FROM stores WHERE 1 = 0", fetch=10)
    assert result == QueryResult(("name",), ())


@pytest.mark.parametrize(
    ("fetch", "expected"),
    [
        (1, ((1,),)),
        (3, ((1,), (2,), (3,))),
        (5, ((1,), (2,), (3,), (4,), (5,))),
        (50, ((1,), (2,), (3,), (4,), (5,))),
    ],
)
def test_qry_r005_reads_at_most_the_rows_to_fetch(
    db_path: Path, fetch: int, expected: tuple[tuple[int], ...]
) -> None:
    """QRY-R005 매출 DB 는 가져올 행 수만큼만 돌려준다 — 행이 더 있어도."""
    result = database(db_path).execute("SELECT store_id FROM stores ORDER BY store_id", fetch=fetch)
    assert result == QueryResult(("store_id",), expected)


def test_qry_r005_does_not_read_past_the_rows_to_fetch(db_path: Path) -> None:
    """QRY-R005 가져올 행 수까지만 읽는다 — 다 읽은 뒤 자르지 않는다 (메모리, NFR-004).

    끝없이 행을 내는 질의로 본다. 다 읽으려는 구현은 제한 시간에 끊겨 실패를 낸다.
    """
    endless_rows = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT x FROM n"
    result = database(db_path, timeout_seconds=1).execute(endless_rows, fetch=3)
    assert result == QueryResult(("x",), ((1,), (2,), (3,)))


# --- QRY-R008 읽기 전용 · QRY-R009 제한 시간 --------------------------------


@pytest.mark.parametrize(
    "sql",
    ["DELETE FROM stores", "INSERT INTO ab_items VALUES (1, 1.0)", "DROP TABLE ab_items"],
    ids=["delete", "insert", "drop"],
)
def test_qry_r008_write_is_refused_by_the_database(db_path: Path, sql: str) -> None:
    """QRY-R008 판정을 거치지 않은 쓰기를 직접 넣어도 DB 가 거부하고, 데이터는 그대로다."""
    db = database(db_path)
    failure = db.execute(sql, fetch=10)
    assert isinstance(failure, ExecutionFailure)
    assert failure.kind is ExecutionFailureKind.REFUSED
    assert db.execute("SELECT COUNT(*) FROM stores", fetch=10) == QueryResult(
        ("COUNT(*)",), ((5,),)
    )
    assert db.tables()[1].name == "ab_items"


def test_qry_r009_heavy_query_is_interrupted_as_timeout(db_path: Path) -> None:
    """QRY-R009 제한 시간을 넘는 질의는 끊기고 실행 실패(시간 초과)가 된다."""
    failure = database(db_path, timeout_seconds=1).execute(ENDLESS, fetch=10)
    assert isinstance(failure, ExecutionFailure)
    assert failure.kind is ExecutionFailureKind.TIMEOUT


def test_query_within_the_timeout_finishes(db_path: Path) -> None:
    """위 테스트의 짝 — 같은 제한 시간 안에 끝나는 질의는 끊지 않는다.

    시간을 살피는 처리기가 여러 번 불릴 만큼(재귀 1만 행) 무겁게 둔다. 너무 가벼운 질의는
    처리기가 한 번도 불리지 않아, 늘 끊는 구현도 통과시킨다.
    """
    counted = (
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 10000) "
        "SELECT COUNT(*) FROM n"
    )
    result = database(db_path, timeout_seconds=1).execute(counted, fetch=10)
    assert result == QueryResult(("COUNT(*)",), ((10000,),))


def test_qry_r009_timeout_after_the_first_row_is_also_a_timeout(db_path: Path) -> None:
    """QRY-R009 첫 행은 바로 나오고 다음 행을 찾다 시간이 넘어도 시간 초과 실패가 된다.

    행을 읽는 중에 끊겨도 예외로 새지 않고 실패 모델로 돌아온다 (설계서 5.2).
    """
    first_row_then_endless = (
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) "
        "SELECT x FROM n WHERE x = 1 OR x < 0"
    )
    failure = database(db_path, timeout_seconds=1).execute(first_row_then_endless, fetch=3)
    assert isinstance(failure, ExecutionFailure)
    assert failure.kind is ExecutionFailureKind.TIMEOUT


# --- N+1 (테스트 규칙 7.3) -------------------------------------------------


def make_db(path: Path, script: str) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(script)
    conn.commit()
    conn.close()
    return path


def test_table_list_asks_the_database_the_same_number_of_times_for_1_or_3_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """표 목록은 표가 1개든 3개든 DB 에 같은 수의 질의를 낸다 — 표마다 따로 묻지 않는다.

    몇 번인지는 단언하지 않는다. 연결에 질의 기록을 걸어 두 경우를 견준다. SQLite 는 표 값
    함수(`pragma_table_info`) 안에서 도는 일도 `-- ` 로 시작하는 줄로 기록하는데, 그것은 질의
    하나 안의 일이라 세지 않는다.
    """
    one = make_db(tmp_path / "one.db", "CREATE TABLE zzz_a (a INTEGER, b TEXT);")
    three = make_db(
        tmp_path / "three.db",
        "CREATE TABLE zzz_a (a INTEGER, b TEXT);"
        "CREATE TABLE zzz_b (a INTEGER, b TEXT);"
        "CREATE TABLE zzz_c (a INTEGER, b TEXT);",
    )
    statements: list[str] = []
    connect = sqlite3.connect

    def record(statement: str) -> None:
        if not statement.startswith("--"):
            statements.append(statement)

    def recording_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn: sqlite3.Connection = connect(*args, **kwargs)
        conn.set_trace_callback(record)
        return conn

    monkeypatch.setattr(sqlite3, "connect", recording_connect)

    assert len(database(one).tables()) == 1
    with_one = len(statements)
    statements.clear()
    assert len(database(three).tables()) == 3
    assert len(statements) == with_one


# --- QRY-R015 별칭의 표 없음 -----------------------------------------------


def test_qry_r015_missing_alias_becomes_its_failure(db_path: Path) -> None:
    """QRY-R015 `no such column: 별칭.열` 을 그 별칭의 실행 실패로 옮긴다.

    세부는 DB 가 준 말이다.
    """
    failure = database(db_path).execute("SELECT zq.region FROM stores s", fetch=10)
    assert isinstance(failure, ExecutionFailure)
    assert (failure.kind, failure.alias) == (ExecutionFailureKind.MISSING_ALIAS, "zq")
    assert "zq.region" in failure.detail


@pytest.mark.parametrize(
    ("sql", "in_detail"),
    [
        ("SELECT * FROM zzz_receipts", "zzz_receipts"),
        ("SELECT zzz_col FROM stores", "zzz_col"),
    ],
    ids=["no-table", "unqualified-column"],
)
def test_other_refusal_has_no_alias(db_path: Path, sql: str, in_detail: str) -> None:
    """위 테스트의 짝 — 별칭이 붙지 않은 오류는 그 밖의 거부이고 별칭이 없다."""
    failure = database(db_path).execute(sql, fetch=10)
    assert isinstance(failure, ExecutionFailure)
    assert (failure.kind, failure.alias) == (ExecutionFailureKind.REFUSED, None)
    assert in_detail in failure.detail


# --- 설정 (설계서 5.3) ----------------------------------------------------


def test_missing_database_file_stops_startup(tmp_path: Path) -> None:
    """DB 파일이 없으면 서버가 뜨지 않는다 — 매출 DB 를 만들 때 실패한다."""
    with pytest.raises(FileNotFoundError):
        SqliteSalesDatabase(tmp_path / "zzz_missing.db", timeout_seconds=5)
