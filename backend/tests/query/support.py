"""질의 도메인 테스트가 함께 쓰는 단언."""

from __future__ import annotations

import json
from typing import Any


def assert_reason(reason: object) -> str:
    """사유가 글이고 비어 있지 않은지 본다. None · 빈 글 · 공백뿐인 글이면 실패한다.

    사유 문구는 설계서가 정하지 않으므로 글자를 견주지 않는다 (테스트 규칙 3절).
    """
    assert isinstance(reason, str)
    assert reason.strip() != ""
    return reason


def read_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    """SSE 본문을 (이벤트 이름, data 의 JSON) 목록으로 읽는다 (설계서 2.2).

    줄 꼴은 엄격히 본다 — 이벤트마다 `event: ` 줄과 `data: ` 줄 둘이고 빈 줄로 끝난다. 화면의
    해석기(`frontend/src/api/sse.ts`)가 그 접두어를 글자로 찾는다. JSON 의 띄어쓰기 · 이스케이프는
    화면이 `JSON.parse` 로 읽어 상관없으므로 풀어서 견준다.
    """
    assert body.endswith("\n\n")
    events = []
    for block in body.removesuffix("\n\n").split("\n\n"):
        event_line, data_line = block.split("\n")
        assert event_line.startswith("event: ")
        assert data_line.startswith("data: ")
        data = json.loads(data_line.removeprefix("data: "))
        events.append((event_line.removeprefix("event: "), data))
    return events
