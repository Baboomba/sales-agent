"""매출 DB 구현. 읽기 전용 SQLite 연결.

바깥(SQLite 의 행 · 오류)을 실행 결과 · 실행 실패로 옮기기만 한다. 실패를 어떻게 안내할지는
규칙이 정한다 (설계서 5.2).
"""

from __future__ import annotations

import re
import sqlite3
import time
from contextlib import closing
from itertools import groupby
from pathlib import Path

from app.query.model.failure import ExecutionFailure, ExecutionFailureKind
from app.query.model.question import Column, Table
from app.query.model.run import QueryResult

# 진행 처리기를 부르는 간격(가상 머신 명령 수). 작을수록 제한 시간에 정확하지만 느려진다.
_PROGRESS_STEPS = 1_000

# 일반 표와 열을 한 번에 읽는다 — 표마다 열을 따로 묻지 않는다(N+1). 내부 표 · 뷰는 뺀다 (QRY-R017).
_TABLES_AND_COLUMNS = """
    SELECT m.name, p.name, p.type
    FROM sqlite_master AS m JOIN pragma_table_info(m.name) AS p
    WHERE m.type = 'table' AND substr(m.name, 1, 7) != 'sqlite_'
    ORDER BY m.rowid, p.cid
"""

_MISSING_ALIAS = re.compile(r"no such column: (\w+)\.\w+")


class SqliteSalesDatabase:
    def __init__(self, path: Path, *, timeout_seconds: float) -> None:
        # 설계서 5.3 — DB 파일이 없으면 서버가 뜨지 않는다.
        if not path.exists():
            raise FileNotFoundError(
                f"DB 파일이 없습니다: {path}. backend/scripts/seed.py 로 만드세요."
            )
        self._uri = f"{path.resolve().as_uri()}?mode=ro"
        self._timeout = timeout_seconds

    def tables(self) -> tuple[Table, ...]:
        with closing(self._connect()) as conn:
            rows = conn.execute(_TABLES_AND_COLUMNS).fetchall()
        return tuple(
            Table(name=name, columns=tuple(Column(name=c[1], type=c[2]) for c in columns))
            for name, columns in groupby(rows, key=lambda row: row[0])
        )

    def execute(self, sql: str, fetch: int) -> QueryResult | ExecutionFailure:
        deadline = time.monotonic() + self._timeout

        def interrupt() -> int:
            # QRY-R009 0 이 아닌 값을 돌려주면 SQLite 가 실행을 끊는다.
            return 1 if time.monotonic() > deadline else 0

        with closing(self._connect()) as conn:
            conn.set_progress_handler(interrupt, _PROGRESS_STEPS)
            try:
                cursor = conn.execute(sql)
                # QRY-R005 가져올 행 수까지만 읽는다. 다 읽고 자르면 큰 결과가 메모리에 다 올라온다.
                rows = tuple(tuple(row) for row in cursor.fetchmany(fetch))
            except sqlite3.Error as error:
                return _failure(error)
            columns = tuple(description[0] for description in cursor.description or ())
        return QueryResult(columns=columns, rows=rows)

    def _connect(self) -> sqlite3.Connection:
        # QRY-R008 읽기 전용으로 연다. 판정이 뚫려도 쓰기는 DB 가 거부한다.
        conn = sqlite3.connect(self._uri, uri=True)
        conn.execute("PRAGMA query_only = ON")
        return conn


def _failure(error: sqlite3.Error) -> ExecutionFailure:
    detail = str(error)
    if isinstance(error, sqlite3.OperationalError) and detail == "interrupted":
        return ExecutionFailure(ExecutionFailureKind.TIMEOUT, detail)
    # QRY-R015 `no such column: 별칭.열` — 어떻게 안내할지는 규칙이 정한다. 여기서는 별칭만 옮긴다.
    missing = _MISSING_ALIAS.search(detail)
    if missing:
        return ExecutionFailure(ExecutionFailureKind.MISSING_ALIAS, detail, alias=missing.group(1))
    return ExecutionFailure(ExecutionFailureKind.REFUSED, detail)
