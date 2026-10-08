"""질문과 데이터 (설계서 5.1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    """사용자가 적은 물음."""

    text: str


@dataclass(frozen=True)
class Column:
    """표의 열. 업무 설명은 용어에서 붙고, 없으면 비어 있다."""

    name: str
    type: str
    description: str = ""


@dataclass(frozen=True)
class Table:
    """물어볼 수 있는 표."""

    name: str
    columns: tuple[Column, ...]
    description: str = ""
