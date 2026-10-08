"""Ollama 에 닿는 얇은 연결. 생성기 구현에 넘길 `Complete` 를 만든다.

언어 모델을 부르는 자리라 단위 테스트하지 않는다(NFR-005). 이 연결이 맞는지는 평가 세트가 본다
(`scripts/eval.sh`). 연결 제한 시간만은 모델 없이 통합 테스트가 본다.
옮기기 · 해석은 생성기 구현이 한다.
"""

from __future__ import annotations

import httpx
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from app.query.dependency.impl.ollama_generator import Complete


def ollama_complete(*, base_url: str, model: str, generation_timeout_seconds: float) -> Complete:
    # 생성 제한 시간은 생성기가 생성 한 번 전체에 건다. 여기서는 연결에만 제한 시간을 건다 —
    # 연결하다 넘은 시간은 연결 실패다 (QRY-R013, #48). 생성 제한 시간과 같으면 어느 쪽이 먼저
    # 터질지 정해지지 않으므로 그 절반으로 둔다. 응답 조각을 기다리는 시간에는 걸지 않는다.
    connect = httpx.Timeout(None, connect=generation_timeout_seconds / 2)
    chat = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,  # 같은 질문에 같은 SQL — 평가 결과가 흔들리지 않게
        format="json",  # QRY-R010 출력 형식을 서버 쪽에서도 강제한다
        num_predict=512,
        client_kwargs={"timeout": connect},
    )

    async def complete(prompt: str) -> str:
        message = await chat.ainvoke([HumanMessage(content=prompt)])
        content = message.content
        return content if isinstance(content, str) else str(content)

    return complete
