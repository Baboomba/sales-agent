"""시드 데이터. 데이터 정의(docs/design/data.md 2절)가 실제 데이터에서 뜻이 있는지 본다.

정의가 가르는 차이 — 정가와 판매 단가, 주문과 주문 상품 줄, 숫자와 문자열 — 가 데이터에
실제로 있어야 정의가 지켜졌는지 평가로 가릴 수 있다.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from scripts.seed import build

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> Iterator[sqlite3.Connection]:
    path = tmp_path_factory.mktemp("seed") / "sales.db"
    build(path)
    conn = sqlite3.connect(path)
    yield conn
    conn.close()


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    value: int = conn.execute(sql).fetchone()[0]
    return value


def test_dat_r001_sale_price_differs_from_list_price_so_revenue_differs(
    seeded: sqlite3.Connection,
) -> None:
    """DAT-R001 판매 단가가 정가와 다른 줄이 있어, 정가로 센 매출은 정의의 매출과 다르다."""
    discounted = scalar(
        seeded,
        "SELECT COUNT(*) FROM order_items oi "
        "JOIN products p ON p.product_id = oi.product_id WHERE oi.unit_price <> p.unit_price",
    )
    revenue = scalar(seeded, "SELECT SUM(quantity * unit_price) FROM order_items")
    with_list_price = scalar(
        seeded,
        "SELECT SUM(oi.quantity * p.unit_price) FROM order_items oi "
        "JOIN products p ON p.product_id = oi.product_id",
    )
    assert discounted > 0
    assert revenue < with_list_price


def test_dat_r002_rows_after_joining_items_outnumber_orders(seeded: sqlite3.Connection) -> None:
    """DAT-R002 주문 상품을 붙여 센 줄 수는 주문 건수보다 많다 — 주문 하나에 상품이 여럿이다."""
    orders = scalar(seeded, "SELECT COUNT(*) FROM orders")
    distinct = scalar(
        seeded,
        "SELECT COUNT(DISTINCT o.order_id) FROM orders o "
        "JOIN order_items oi ON oi.order_id = o.order_id",
    )
    joined_rows = scalar(
        seeded, "SELECT COUNT(*) FROM orders o JOIN order_items oi ON oi.order_id = o.order_id"
    )
    assert distinct == orders
    assert joined_rows > orders


def test_dat_r003_strftime_matches_strings_but_never_numbers(seeded: sqlite3.Connection) -> None:
    """DAT-R003 주말 주문을 숫자로 견주면 한 건도 걸리지 않고, 문자열로 견주면 걸린다."""
    as_numbers = scalar(
        seeded, "SELECT COUNT(*) FROM orders WHERE strftime('%w', ordered_on) IN (0, 6)"
    )
    as_strings = scalar(
        seeded, "SELECT COUNT(*) FROM orders WHERE strftime('%w', ordered_on) IN ('0', '6')"
    )
    assert as_numbers == 0
    assert as_strings > 0


def build_in_new_process(path: Path, hash_seed: str) -> None:
    """새 프로세스에서 시드 데이터를 만든다. 문자열 해시 순서도 프로세스마다 다르게 준다."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; "
            "from scripts.seed import build; build(Path(sys.argv[1]))",
            str(path),
        ],
        cwd=BACKEND,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
        check=True,
        capture_output=True,
    )


def test_dat_r004_same_seed_builds_the_same_data(tmp_path: Path) -> None:
    """DAT-R004 같은 시드로 두 번 만든 데이터의 내용이 같다.

    프로세스마다 달라지는 것(프로세스 번호 · 문자열 해시 순서)에 기대도 걸리게 따로 만든다.
    """
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    build_in_new_process(first, "1")
    build_in_new_process(second, "2")

    def dump(path: Path) -> list[str]:
        conn = sqlite3.connect(path)
        try:
            return list(conn.iterdump())
        finally:
            conn.close()

    first_dump = dump(first)
    assert len(first_dump) > 1000
    assert first_dump == dump(second)
