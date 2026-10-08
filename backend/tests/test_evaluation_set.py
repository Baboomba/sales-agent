"""평가 세트의 정답이 데이터 정의(docs/design/data.md 2절)를 따르는지."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlglot
import yaml
from sqlglot import exp

QUESTIONS = Path(__file__).resolve().parents[1] / "evaluation" / "questions.yaml"
AGGREGATES = (exp.Sum, exp.Avg, exp.Anonymous)  # TOTAL 은 sqlglot 이 이름 없는 함수로 읽는다


def gold_sql() -> dict[str, str]:
    items: list[dict[str, Any]] = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    return {item["id"]: item["sql"] for item in items}


def _table_of(column: exp.Column, tables: dict[str, str]) -> str:
    """열이 가리키는 표 이름. 한정자가 없으면 정가를 가진 표가 products 뿐일 때만 products 다."""
    if column.table:
        return tables.get(column.table, column.table)
    names = set(tables.values())
    return "products" if "products" in names and "order_items" not in names else ""


def counts_money_with_list_price(sql: str) -> bool:
    """정가(products.unit_price)를 곱하거나 더해 돈을 세는지.

    별칭 · 중첩 괄호 · 공통 식(WITH)에서 곱해 둔 열까지 본다. 「가장 비싼 상품」처럼 정가 자체를
    고르기만 하는 것은 세지 않는다.
    """
    tree = sqlglot.parse_one(sql, read="sqlite")
    tables = {table.alias_or_name: table.name for table in tree.find_all(exp.Table)}
    for column in tree.find_all(exp.Column):
        if column.name != "unit_price" or _table_of(column, tables) != "products":
            continue
        if column.find_ancestor(exp.Mul, *AGGREGATES) is not None:
            return True
    return False


def test_dat_r001_gold_answers_never_count_revenue_with_the_list_price() -> None:
    """DAT-R001 평가 세트의 정답은 정가(products.unit_price)로 매출을 세지 않는다."""
    answers = gold_sql()
    assert len(answers) >= 10
    assert [qid for qid, sql in answers.items() if counts_money_with_list_price(sql)] == []


def test_list_price_check_catches_every_spelling() -> None:
    """검사가 헛돌지 않게 — 정가로 돈을 세는 여러 꼴을 모두 잡는다."""
    join = "FROM order_items oi JOIN products {p} ON {p}.product_id = oi.product_id"
    assert counts_money_with_list_price(
        f"SELECT SUM(oi.quantity * p.unit_price) {join.format(p='p')}"
    )
    assert counts_money_with_list_price(
        f"SELECT SUM(CAST(oi.quantity AS REAL) * pr.unit_price) {join.format(p='pr')}"
    )
    assert counts_money_with_list_price(
        f"SELECT TOTAL(oi.quantity * products.unit_price) {join.format(p='products')}"
    )
    assert counts_money_with_list_price(
        f"WITH x AS (SELECT oi.quantity * p.unit_price AS amt {join.format(p='p')}) "
        "SELECT SUM(amt) FROM x"
    )
    assert counts_money_with_list_price("SELECT SUM(unit_price) FROM products")


def test_list_price_check_lets_sale_price_and_plain_list_price_through() -> None:
    """위의 짝 — 판매 단가로 센 매출과, 정가를 고르기만 하는 것은 잡지 않는다."""
    assert not counts_money_with_list_price(
        "SELECT SUM(oi.quantity * oi.unit_price) FROM order_items oi "
        "JOIN products p ON p.product_id = oi.product_id"
    )
    assert not counts_money_with_list_price("SELECT SUM(quantity * unit_price) FROM order_items")
    assert not counts_money_with_list_price(
        "SELECT name, unit_price FROM products ORDER BY unit_price DESC LIMIT 1"
    )
