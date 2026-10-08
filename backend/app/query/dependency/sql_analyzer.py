"""SQL 분석기 — 생성 SQL 을 업무 말(SQL 구성)로 옮긴다 (설계서 5.2)."""

from __future__ import annotations

from typing import Protocol

from app.query.model.sql import SqlShape


class SqlAnalyzer(Protocol):
    def analyze(self, sql: str) -> SqlShape:
        """생성 SQL 의 글을 SQL 구성으로 옮긴다. 분석하지 못하면 분석 오류를 담아 돌려준다."""
        ...

    def attach_limit(self, sql: str, limit: int) -> str:
        """바깥 행 상한을 붙인 SQL 글. 판정을 통과한 SQL 에만 부른다."""
        ...
