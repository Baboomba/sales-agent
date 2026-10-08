"""질의 도메인 테스트가 함께 쓰는 가짜 (테스트 규칙 7.1 — 도메인마다 한 자리).

가짜는 정해 둔 답을 차례로 돌려주고, 받은 것을 기록하기만 한다. 판단을 넣지 않는다 (5절).
"""

from __future__ import annotations

from collections.abc import Iterable


class ScriptedModel:
    """언어 모델 대신 쓴다. 답 자리에 예외를 두면 그 차례에 그 예외를 던진다."""

    def __init__(self, replies: Iterable[str | Exception]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
