"""SalesDatabase 구현. 읽기 전용 SQLite 연결."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from app.query.model import Column, QueryResult, Table
from app.query.ports import ExecutionError

# 진행 처리기를 부르는 간격(가상 머신 명령 수). 작을수록 제한 시간에 정확하지만 느려진다.
_PROGRESS_STEPS = 1_000


class SqliteSalesDatabase:
    def __init__(self, path: Path, *, timeout_seconds: float) -> None:
        if not path.exists():
            raise FileNotFoundError(f"DB 파일이 없습니다: {path}. scripts/seed.py 로 만드세요.")
        self._path = path
        self._timeout = timeout_seconds

    def schema(self) -> tuple[Table, ...]:
        with self._connect() as conn:
            names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
                )
            ]
            return tuple(
                Table(
                    name=name,
                    columns=tuple(
                        Column(name=col[1], type=col[2])
                        for col in conn.execute(f"PRAGMA table_info('{name}')")
                    ),
                )
                for name in names
            )

    def execute(self, sql: str) -> QueryResult:
        deadline = time.monotonic() + self._timeout

        def interrupt() -> int:
            # QRY-R009 0 이 아닌 값을 돌려주면 SQLite 가 실행을 끊는다.
            return 1 if time.monotonic() > deadline else 0

        with self._connect() as conn:
            conn.set_progress_handler(interrupt, _PROGRESS_STEPS)
            try:
                cursor = conn.execute(sql)
                rows = tuple(tuple(row) for row in cursor.fetchall())
            except sqlite3.OperationalError as error:
                if "interrupted" in str(error):
                    message = f"실행 시간이 {self._timeout:g}초를 넘어 중단했습니다."
                    raise ExecutionError(f"{message} 더 가벼운 질의로 바꾸세요.") from error
                raise ExecutionError(str(error)) from error
            except sqlite3.Error as error:
                raise ExecutionError(str(error)) from error
            columns = tuple(d[0] for d in cursor.description or ())
            return QueryResult(columns=columns, rows=rows)

    def _connect(self) -> sqlite3.Connection:
        # QRY-R008 읽기 전용으로 연다. 검증이 뚫려도 쓰기는 DB 가 거부한다.
        conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        return conn
