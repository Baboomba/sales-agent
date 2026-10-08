"""가상의 2025년 매출 데이터를 만든다.

같은 시드면 같은 파일이 나온다. 평가 세트의 정답이 이 데이터에 묶여 있으므로
시드나 분포를 바꾸면 평가 세트를 다시 확인해야 한다.

    uv run python scripts/seed.py
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SEED = 2025
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sales.db"

STORES = [
    ("강남점", "서울", "2019-03-02"),
    ("홍대점", "서울", "2020-07-15"),
    ("잠실점", "서울", "2021-05-01"),
    ("여의도점", "서울", "2022-09-20"),
    ("판교점", "경기", "2020-11-11"),
    ("수원점", "경기", "2021-02-14"),
    ("일산점", "경기", "2023-04-08"),
    ("해운대점", "부산", "2019-08-30"),
    ("서면점", "부산", "2022-01-21"),
    ("동성로점", "대구", "2020-05-05"),
    ("충장로점", "광주", "2021-10-10"),
    ("둔산점", "대전", "2023-06-17"),
]

PRODUCTS = [
    ("클래식 버거", "버거", 6500),
    ("치즈 버거", "버거", 7000),
    ("베이컨 버거", "버거", 7900),
    ("불고기 버거", "버거", 6900),
    ("치킨 버거", "버거", 7200),
    ("새우 버거", "버거", 7500),
    ("감자튀김", "사이드", 2500),
    ("치즈스틱", "사이드", 2800),
    ("어니언링", "사이드", 3000),
    ("너겟", "사이드", 3500),
    ("콜라", "음료", 2000),
    ("사이다", "음료", 2000),
    ("아이스티", "음료", 2500),
    ("아메리카노", "음료", 3000),
    ("밀크쉐이크", "음료", 4000),
    ("아이스크림", "디저트", 2000),
    ("애플파이", "디저트", 2500),
    ("초코쿠키", "디저트", 1800),
]

CHANNELS = [("매장", 0.5), ("배달", 0.35), ("포장", 0.15)]

# 매장마다 하루 평균 주문 수. 매장 간 차이를 뚜렷하게 둬야 "상위 매장" 질문의 답이 흔들리지 않는다.
DAILY_ORDERS = [62, 48, 40, 30, 44, 35, 22, 50, 28, 33, 25, 18]

# 달마다 계절 가중치. 여름에 음료·디저트가, 겨울에 버거가 잘 팔린다.
SUMMER_MONTHS = {6, 7, 8}
WINTER_MONTHS = {12, 1, 2}

SCHEMA = """
CREATE TABLE stores (
    store_id   INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    region     TEXT    NOT NULL,
    opened_on  TEXT    NOT NULL
);
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    category   TEXT    NOT NULL,
    unit_price INTEGER NOT NULL
);
CREATE TABLE orders (
    order_id   INTEGER PRIMARY KEY,
    store_id   INTEGER NOT NULL REFERENCES stores(store_id),
    ordered_on TEXT    NOT NULL,
    channel    TEXT    NOT NULL
);
CREATE TABLE order_items (
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity   INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,
    PRIMARY KEY (order_id, product_id)
);
CREATE INDEX idx_orders_store_date ON orders(store_id, ordered_on);
CREATE INDEX idx_order_items_product ON order_items(product_id);
"""


def _pick_channel(rng: random.Random) -> str:
    return rng.choices([c for c, _ in CHANNELS], weights=[w for _, w in CHANNELS])[0]


def _category_weight(category: str, month: int) -> float:
    if month in SUMMER_MONTHS and category in ("음료", "디저트"):
        return 1.6
    if month in WINTER_MONTHS and category == "버거":
        return 1.3
    return 1.0


def _pick_items(rng: random.Random, month: int) -> list[tuple[int, int, int]]:
    """한 주문의 (product_id, quantity, unit_price) 목록."""
    weights = [_category_weight(cat, month) for _, cat, _ in PRODUCTS]
    count = rng.choices([1, 2, 3, 4], weights=[0.25, 0.4, 0.25, 0.1])[0]
    product_ids = set()
    while len(product_ids) < count:
        product_ids.add(rng.choices(range(1, len(PRODUCTS) + 1), weights=weights)[0])
    items = []
    for product_id in sorted(product_ids):
        list_price = PRODUCTS[product_id - 1][2]
        # 열에 하나 꼴로 10% 할인. 매출을 정가로 셈하면 틀리게 만드는 장치다.
        price = int(list_price * 0.9) if rng.random() < 0.1 else list_price
        quantity = rng.choices([1, 2, 3], weights=[0.7, 0.22, 0.08])[0]
        items.append((product_id, quantity, price))
    return items


def build(path: Path = DB_PATH) -> None:
    rng = random.Random(SEED)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO stores (store_id, name, region, opened_on) VALUES (?, ?, ?, ?)",
        [(i + 1, *s) for i, s in enumerate(STORES)],
    )
    conn.executemany(
        "INSERT INTO products (product_id, name, category, unit_price) VALUES (?, ?, ?, ?)",
        [(i + 1, *p) for i, p in enumerate(PRODUCTS)],
    )

    order_id = 0
    orders: list[tuple[int, int, str, str]] = []
    items: list[tuple[int, int, int, int]] = []
    day = date(2025, 1, 1)
    while day.year == 2025:
        weekend = day.weekday() >= 5
        for store_index, base in enumerate(DAILY_ORDERS):
            mean = base * (1.3 if weekend else 1.0)
            count = max(0, int(rng.gauss(mean, mean * 0.15)))
            for _ in range(count):
                order_id += 1
                orders.append((order_id, store_index + 1, day.isoformat(), _pick_channel(rng)))
                for product_id, quantity, price in _pick_items(rng, day.month):
                    items.append((order_id, product_id, quantity, price))
        day += timedelta(days=1)

    conn.executemany(
        "INSERT INTO orders (order_id, store_id, ordered_on, channel) VALUES (?, ?, ?, ?)", orders
    )
    conn.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
        items,
    )
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    print(f"{path} — 주문 {len(orders):,}건, 주문 상품 {len(items):,}건")


if __name__ == "__main__":
    build()
