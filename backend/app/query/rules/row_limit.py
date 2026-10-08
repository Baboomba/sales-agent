"""행 상한 (설계서 3절)."""

from __future__ import annotations

from dataclasses import replace

from app.query.model.run import QueryResult


def limit_to_attach(outer_limit: int | None, row_limit: int) -> int | None:
    """QRY-R005 붙일 행 상한. 바깥 행 상한이 0 이상 상한 이하면 None(그대로), 아니면 상한+1.

    한 행 더 가져와야, 결과가 정확히 상한 개수일 때 잘린 것인지 아닌지 안다.
    음수는 SQLite 가 상한 없음으로 풀므로 없는 것과 같이 다룬다.
    """
    if outer_limit is not None and 0 <= outer_limit <= row_limit:
        return None
    return row_limit + 1


def rows_to_fetch(row_limit: int) -> int:
    """QRY-R005 매출 DB 가 가져올 행 수. 상한보다 하나 더 — 잘렸는지 알 수 있게."""
    return row_limit + 1


def cap_rows(result: QueryResult, row_limit: int) -> QueryResult:
    """QRY-R005 상한을 넘은 결과를 상한만큼 잘라 내고 잘렸다고 표시한다."""
    return replace(result, rows=result.rows[:row_limit], truncated=len(result.rows) > row_limit)
