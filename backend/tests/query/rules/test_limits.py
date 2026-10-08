"""질의 한도."""

from __future__ import annotations

import pytest

from app.query.model.failure import QueryLimits
from app.query.rules.limits import check_limits
from tests.query.support import assert_reason


def limits(generation: float, query: float, attempts: int = 3) -> QueryLimits:
    return QueryLimits(
        max_attempts=attempts,
        row_limit=200,
        generation_timeout_seconds=generation,
        query_timeout_seconds=query,
    )


def test_qry_r016_default_limits_are_accepted() -> None:
    """QRY-R016 기본 한도 3 × (15 + 5) = 60초는 받는다."""
    assert check_limits(limits(15, 5)) is None


@pytest.mark.parametrize(("generation", "query"), [(30, 5), (15, 5.1)], ids=["105초", "60.3초"])
def test_qry_r016_over_60_seconds_is_refused(generation: float, query: float) -> None:
    """QRY-R016 생성 제한 시간 30초(3 × (30 + 5) = 105초)도, 60초를 조금 넘는 한도도 받지 않는다."""
    assert_reason(check_limits(limits(generation, query)))


def test_fewer_attempts_allow_longer_timeouts() -> None:
    assert check_limits(limits(25, 5, attempts=2)) is None
