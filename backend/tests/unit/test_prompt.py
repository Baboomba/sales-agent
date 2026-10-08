"""프롬프트 조립. 모델이 자주 틀리는 자리를 프롬프트가 담고 있는지 확인한다.

프롬프트의 내용은 규칙이 아니라 평가 세트가 품질을 잰다(NFR-006). 그래서 여기 테스트는
「프롬프트에 무엇이 들어가는가」만 보고, 규칙 ID 는 실제로 규칙을 확인하는 곳에만 적는다.
"""

from __future__ import annotations

from app.query.model import Column, Table
from app.query.prompt import build_prompt
from tests.fakes import TABLES


def test_prompt_contains_the_question() -> None:
    prompt = build_prompt("강남점 매출은?", TABLES, feedback=None)
    assert "질문: 강남점 매출은?" in prompt


def test_prompt_describes_the_given_tables() -> None:
    """넘긴 표의 이름과 열이 들어간다. 고정 문구에 없는 이름으로 확인한다."""
    tables = (Table(name="zzz_receipts", columns=(Column("receipt_id", "INTEGER"),)),)
    prompt = build_prompt("영수증", tables, feedback=None)
    assert "zzz_receipts" in prompt
    assert "receipt_id INTEGER" in prompt


def test_prompt_states_revenue_definition() -> None:
    """매출은 판매 단가 × 수량이다 — 가장 자주 틀리는 자리 (data.md)."""
    prompt = build_prompt("매출", TABLES, feedback=None)
    assert "SUM(order_items.quantity * order_items.unit_price)" in prompt


def test_prompt_states_order_count_definition() -> None:
    """주문 건수는 주문 번호의 개수다 — 평가 1차의 E13 오답 (data.md)."""
    prompt = build_prompt("매출", TABLES, feedback=None)
    assert "COUNT(DISTINCT orders.order_id)" in prompt


def test_prompt_states_strftime_returns_strings() -> None:
    """strftime 결과는 문자열이다 — 평가 1차의 E18 오답 (data.md)."""
    prompt = build_prompt("매출", TABLES, feedback=None)
    assert "'0'(일)~'6'(토)" in prompt


def test_prompt_asks_for_a_json_object() -> None:
    prompt = build_prompt("매출", TABLES, feedback=None)
    assert '{"sql": "SELECT ..."}' in prompt


def test_qry_r006_feedback_is_inserted_before_the_question() -> None:
    """QRY-R006 직전 실패 사유가 있으면 질문 앞에 끼워 넣고, 나머지는 그대로다."""
    reason = "ZZZ 허용되지 않은 표"
    without = build_prompt("매출", TABLES, feedback=None)
    with_feedback = build_prompt("매출", TABLES, feedback=reason)

    head, question = without.rsplit("\n\n", 1)
    assert with_feedback.startswith(head)
    assert with_feedback.endswith(question)
    assert reason in with_feedback[len(head) : -len(question)]
