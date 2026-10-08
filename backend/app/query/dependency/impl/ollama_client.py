"""Ollama 에 닿는 얇은 연결. 생성기 구현에 넘길 `Complete` 를 만든다.

모델 서버가 있어야 도는 자리라 테스트하지 않는다(NFR-005). 이 연결이 맞는지는 평가 세트가 본다
(`scripts/eval.sh`). 그래서 이 파일에는 판단을 두지 않는다 — 옮기기 · 해석은 생성기 구현이 한다.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from app.query.dependency.impl.ollama_generator import Complete


def ollama_complete(*, base_url: str, model: str, timeout_seconds: float) -> Complete:
    chat = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,  # 같은 질문에 같은 SQL — 평가 결과가 흔들리지 않게
        format="json",  # QRY-R010 출력 형식을 서버 쪽에서도 강제한다
        num_predict=512,
        client_kwargs={"timeout": timeout_seconds},
    )

    async def complete(prompt: str) -> str:
        message = await chat.ainvoke([HumanMessage(content=prompt)])
        content = message.content
        return content if isinstance(content, str) else str(content)

    return complete
