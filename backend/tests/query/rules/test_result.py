"""실행 결과 값."""

from __future__ import annotations

from app.query.model.run import QueryResult
from app.query.rules.result import sanitize


def test_qry_r014_byte_values_become_binary_and_others_stay() -> None:
    """QRY-R014 바이트 값만 `<binary>` 로 바뀌고, 다른 값은 DB 가 낸 그대로다.

    `1 == 1.0`, `0 == False` 라 `==` 로는 숫자 타입이 바뀐 것을 모른다. repr 로 견준다.
    바이트 값을 첫 · 가운데 · 끝 행과 열에 하나씩 둔다.
    """
    result = QueryResult(
        columns=("a", "b", "c"),
        rows=(
            (b"\x00", 1, "가"),
            (2.5, bytearray(b"\x01"), None),
            (0, "", memoryview(b"\x02")),
        ),
        truncated=True,
    )
    assert repr(sanitize(result)) == repr(
        QueryResult(
            columns=("a", "b", "c"),
            rows=(
                ("<binary>", 1, "가"),
                (2.5, "<binary>", None),
                (0, "", "<binary>"),
            ),
            truncated=True,
        )
    )
