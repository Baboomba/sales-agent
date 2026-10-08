"""실행 결과 값 (설계서 3절)."""

from __future__ import annotations

from dataclasses import replace

from app.query.model.run import QueryResult

_BINARY = "<binary>"


def sanitize(result: QueryResult) -> QueryResult:
    """QRY-R014 바이트 값을 `<binary>` 로 바꾼다. 나머지 값은 DB 가 낸 그대로 둔다 (NFR-002)."""
    rows = tuple(tuple(_sanitize_value(value) for value in row) for row in result.rows)
    return replace(result, rows=rows)


def _sanitize_value(value: object) -> object:
    if isinstance(value, bytes | bytearray | memoryview):
        return _BINARY
    return value
