"""실제 SQLite 파일로 확인하는 것들. 검증이 뚫렸을 때의 마지막 방어선이다."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.query.adapters.sqlite import SqliteSalesDatabase
from app.query.ports import ExecutionError

pytestmark = pytest.mark.integration


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE stores (store_id INTEGER PRIMARY KEY, name TEXT, region TEXT);
        INSERT INTO stores VALUES (1, '강남점', '서울'), (2, '해운대점', '부산');
        """
    )
    conn.commit()
    conn.close()
    return path


def test_qry_r008_write_is_refused_by_database(db_path: Path) -> None:
    """QRY-R008 검증을 거치지 않은 쓰기를 직접 넣어도 DB 가 거부한다."""
    database = SqliteSalesDatabase(db_path, timeout_seconds=5)
    with pytest.raises(ExecutionError):
        database.execute("DELETE FROM stores")
    assert database.execute("SELECT COUNT(*) FROM stores").rows == ((2,),)


def test_qry_r009_heavy_query_is_interrupted(db_path: Path) -> None:
    """QRY-R009 제한 시간을 넘는 질의는 끊긴다."""
    database = SqliteSalesDatabase(db_path, timeout_seconds=0.2)
    endless = (
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
    )
    with pytest.raises(ExecutionError) as info:
        database.execute(endless)
    assert "시간" in str(info.value)


def test_schema_reads_tables_and_columns(db_path: Path) -> None:
    """FR-006 표와 열 이름 · 타입을 DB 에서 읽는다."""
    database = SqliteSalesDatabase(db_path, timeout_seconds=5)
    (table,) = database.schema()
    assert table.name == "stores"
    assert [c.name for c in table.columns] == ["store_id", "name", "region"]


def test_execute_returns_columns_and_rows(db_path: Path) -> None:
    """FR-001 열 이름과 행을 돌려준다."""
    database = SqliteSalesDatabase(db_path, timeout_seconds=5)
    result = database.execute("SELECT name FROM stores ORDER BY store_id")
    assert result.columns == ("name",)
    assert result.rows == (("강남점",), ("해운대점",))
