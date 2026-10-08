"""실패와 질의 한도 (설계서 5.1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Stage(Enum):
    """실패가 난 단계."""

    GENERATE = "generate"
    VALIDATE = "validate"
    EXECUTE = "execute"


class GenerationFailureKind(Enum):
    FORMAT = "format"  # 출력 형식 오류 — 다시 만들면 나을 수 있다
    CONNECTION = "connection"  # 연결 실패
    ERROR_RESPONSE = "error_response"  # 오류 응답 (모델 없음 등)
    TIMEOUT = "timeout"  # 응답 시간 초과


@dataclass(frozen=True)
class GenerationFailure:
    """생성기가 낸 실패. 세부는 바깥이 준 말 그대로다."""

    kind: GenerationFailureKind
    detail: str


class ExecutionFailureKind(Enum):
    TIMEOUT = "timeout"
    MISSING_ALIAS = "missing_alias"  # 별칭의 표 없음 (no such column: 별칭.열)
    REFUSED = "refused"  # 그 밖의 DB 거부


@dataclass(frozen=True)
class ExecutionFailure:
    """매출 DB 가 낸 실패. 별칭은 「별칭의 표 없음」일 때만 있다."""

    kind: ExecutionFailureKind
    detail: str
    alias: str | None = None


@dataclass(frozen=True)
class QueryLimits:
    """설정에서 온 한도."""

    max_attempts: int
    row_limit: int
    generation_timeout_seconds: float
    query_timeout_seconds: float
