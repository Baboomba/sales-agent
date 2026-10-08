"""표와 열의 업무 설명, 예시 질문. 순수 데이터다.

DB 는 이름과 타입만 안다. 「매출이 무엇인가」 같은 업무 지식은 여기 있다 (docs/design/data.md).
"""

from __future__ import annotations

TABLE_DESCRIPTIONS: dict[str, str] = {
    "stores": "매장",
    "products": "상품",
    "orders": "주문. 한 행이 주문 한 건",
    "order_items": "주문에 담긴 상품. 매출은 이 표로 계산한다",
}

COLUMN_DESCRIPTIONS: dict[tuple[str, str], str] = {
    ("stores", "name"): "매장 이름 (예: 강남점)",
    ("stores", "region"): "지역: 서울, 경기, 부산, 대구, 광주, 대전",
    ("stores", "opened_on"): "개점일 'YYYY-MM-DD'",
    ("products", "name"): "상품 이름",
    ("products", "category"): "분류: 버거, 사이드, 음료, 디저트",
    ("products", "unit_price"): "정가(원). 매출 계산에 쓰지 않는다",
    ("orders", "ordered_on"): "주문일 'YYYY-MM-DD' (2025년)",
    ("orders", "channel"): "주문 경로: 매장, 배달, 포장",
    ("order_items", "quantity"): "수량",
    ("order_items", "unit_price"): "판매 당시 단가(원). 매출 계산에 쓴다",
}

REVENUE_DEFINITION = "매출 = SUM(order_items.quantity * order_items.unit_price)"

# 작은 모델은 예시가 있을 때 정확도가 크게 오른다. 평가 세트와 겹치지 않는 질문만 둔다.
FEW_SHOT: tuple[tuple[str, str], ...] = (
    (
        "2025년 3월 부산 지역 매출은?",
        "SELECT SUM(oi.quantity * oi.unit_price) AS revenue "
        "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
        "JOIN stores s ON s.store_id = o.store_id "
        "WHERE s.region = '부산' AND o.ordered_on BETWEEN '2025-03-01' AND '2025-03-31'",
    ),
    (
        "음료 분류에서 가장 많이 팔린 상품 2개",
        "SELECT p.name, SUM(oi.quantity) AS qty "
        "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
        "WHERE p.category = '음료' GROUP BY p.name ORDER BY qty DESC LIMIT 2",
    ),
)

EXAMPLE_QUESTIONS: tuple[str, ...] = (
    "2025년 지역별 매출을 높은 순으로 보여줘",
    "매출 상위 3개 매장은?",
    "월별 주문 건수 추이",
    "배달 주문 비중이 가장 높은 매장은?",
    "7월에 가장 많이 팔린 디저트는?",
)
