"""행 상한."""

from __future__ import annotations

import pytest

from app.query.model.run import QueryResult
from app.query.rules.row_limit import cap_rows, limit_to_attach


@pytest.mark.parametrize(
    ("outer_limit", "row_limit", "expected"),
    [
        (None, 200, 201),
        (500, 200, 201),
        (201, 200, 201),
        (-1, 200, 201),
        (-5, 200, 201),
        (200, 200, None),
        (10, 200, None),
        (0, 200, None),
        (None, 50, 51),
        (51, 50, 51),
        (-7, 50, 51),
        (50, 50, None),
    ],
)
def test_qry_r005_limit_to_attach(
    outer_limit: int | None, row_limit: int, expected: int | None
) -> None:
    """QRY-R005 바깥 행 상한이 없거나 음수이거나 상한보다 크면 상한+1 을 붙인다.

    0 이상 상한 이하면 그대로 둔다.
    """
    assert limit_to_attach(outer_limit, row_limit) == expected


def test_qry_r005_result_over_the_limit_is_cut_and_marked_truncated() -> None:
    """QRY-R005 상한+1 행이면 상한만큼만 남기고 잘렸다고 알린다."""
    result = QueryResult(columns=("n",), rows=((1,), (2,), (3,)))
    assert cap_rows(result, 2) == QueryResult(columns=("n",), rows=((1,), (2,)), truncated=True)


def test_qry_r005_result_of_exactly_the_limit_is_not_truncated() -> None:
    """QRY-R005 정확히 상한 개수면 잘리지 않았다."""
    result = QueryResult(columns=("n",), rows=((1,), (2,)))
    assert cap_rows(result, 2) == QueryResult(columns=("n",), rows=((1,), (2,)), truncated=False)


def test_empty_result_is_not_truncated() -> None:
    result = QueryResult(columns=("n",), rows=())
    assert cap_rows(result, 2) == QueryResult(columns=("n",), rows=(), truncated=False)
