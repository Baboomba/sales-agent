"""프롬프트 조립. 모델이 자주 틀리는 자리를 프롬프트가 담고 있는지 확인한다."""

from __future__ import annotations

from app.query.prompt import build_prompt
from tests.fakes import TABLES


def test_prompt_contains_question_and_tables() -> None:
    """QRY-R006 프롬프트에 질문과 표 이름이 들어간다."""
    prompt = build_prompt("강남점 매출은?", TABLES, feedback=None)
    assert "강남점 매출은?" in prompt
    assert "stores" in prompt
    assert "orders" in prompt


def test_prompt_states_revenue_definition() -> None:
    """QRY-R006 매출 정의(판매 단가 × 수량)를 프롬프트가 알려 준다 — 가장 자주 틀리는 자리다."""
    prompt = build_prompt("매출", TABLES, feedback=None)
    assert "order_items.quantity * order_items.unit_price" in prompt


def test_prompt_asks_for_json_only() -> None:
    """QRY-R010 출력 형식을 JSON 하나로 못 박는다."""
    prompt = build_prompt("매출", TABLES, feedback=None)
    assert '{"sql":' in prompt


def test_feedback_is_included_only_when_present() -> None:
    """QRY-R006 직전 실패 사유는 있을 때만 붙는다."""
    reason = "ZZZ 허용되지 않은 표"
    assert reason in build_prompt("매출", TABLES, feedback=reason)
    assert "직전 시도" not in build_prompt("매출", TABLES, feedback=None)


def test_prompt_states_order_count_and_strftime_rules() -> None:
    """QRY-R006 평가 1차에서 틀린 자리(주문당 평균 · strftime 비교)를 프롬프트가 알려 준다."""
    prompt = build_prompt("매출", TABLES, feedback=None)
    assert "COUNT(DISTINCT orders.order_id)" in prompt
    assert "'0'(일)~'6'(토)" in prompt
