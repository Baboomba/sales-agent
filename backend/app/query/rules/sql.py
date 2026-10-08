"""SQL 구성 판정 (설계서 3절)."""

from __future__ import annotations

from typing import assert_never

from app.query.model.sql import Accepted, Qualifier, Refused, SqlShape, Verdict
from app.query.rules.row_limit import limit_to_attach


def judge(shape: SqlShape, *, allowed_tables: frozenset[str], row_limit: int) -> Verdict:
    """QRY-R002 ~ QRY-R004 실행해도 되는 SQL 구성인지 판정한다.

    통과하면 붙일 행 상한은 QRY-R005 가 정한다.
    """
    # QRY-R002 분석 오류가 있으면 나머지 필드는 의미가 없다. 가장 먼저 본다.
    if shape.parse_error is not None:
        return Refused(f"SQL 구문 오류입니다: {shape.parse_error}")
    if shape.statement_count != 1:
        return Refused("SQL 은 한 문장이어야 합니다. 세미콜론으로 여러 문장을 잇지 마세요.")
    # QRY-R003
    if not shape.is_query:
        return Refused("조회(SELECT) 문만 실행할 수 있습니다.")
    if shape.forbidden:
        return Refused(f"조회문 안에 허용되지 않은 구문이 있습니다: {', '.join(shape.forbidden)}")
    refused = _refuse_tables(shape, allowed_tables)
    if refused is not None:
        return refused
    return Accepted(limit=limit_to_attach(shape.outer_limit, row_limit))


def _refuse_tables(shape: SqlShape, allowed_tables: frozenset[str]) -> Refused | None:
    """QRY-R004 허용된 표만 참조한다 (NFR-008).

    표 값 함수는 언제나 거부한다. 다른 스키마의 표도 거부한다. 기본 스키마를 붙인 이름은 CTE 가
    아니므로 실제 허용 표만 받고, 한정자가 없을 때만 CTE 이름을 허용된 표로 친다.
    이름은 대소문자를 가리지 않는다.
    """
    real = {name.lower() for name in allowed_tables}
    real_or_cte = real | {name.lower() for name in shape.cte_names}
    tail = f"쓸 수 있는 표: {', '.join(sorted(allowed_tables))}"
    for ref in shape.tables:
        if ref.is_function:
            return Refused(f"FROM 자리에 함수를 쓸 수 없습니다. {tail}")
        match ref.qualifier:
            case Qualifier.OTHER_SCHEMA:
                return Refused(f"다른 스키마의 표는 쓸 수 없습니다: {ref.name}. {tail}")
            case Qualifier.DEFAULT_SCHEMA:
                known = real
            case Qualifier.NONE:
                known = real_or_cte
            case _:
                # 한정자 종류가 늘면 mypy 가 여기서 멈춘다. 새 종류를 허용 표로 흘려보내지 않는다.
                assert_never(ref.qualifier)
        if ref.name.lower() not in known:
            return Refused(f"허용되지 않은 표입니다: {ref.name}. {tail}")
    return None
