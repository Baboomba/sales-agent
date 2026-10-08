"""실행 결과 값 (설계서 3절)."""

from __future__ import annotations

from dataclasses import replace

from app.query.model.run import QueryResult

_BINARY = "<binary>"
_INFINITY = float("inf")


def sanitize(result: QueryResult) -> QueryResult:
    """QRY-R014 JSON 이 받지 못하는 값을 바꾼다. 나머지 값은 DB 가 낸 그대로 둔다 (NFR-002).

    바이트 값은 `<binary>`, 무한대는 `Infinity` · `-Infinity` 글이 된다.
    NaN 은 SQLite 가 NULL 로 내므로 오지 않는다.
    """
    rows = tuple(tuple(_sanitize_value(value) for value in row) for row in result.rows)
    return replace(result, rows=rows)


def _sanitize_value(value: object) -> object:
    if isinstance(value, bytes | bytearray | memoryview):
        return _BINARY
    if value == _INFINITY:
        return "Infinity"
    if value == -_INFINITY:
        return "-Infinity"
    return value
