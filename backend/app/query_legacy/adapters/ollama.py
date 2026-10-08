"""SqlGenerator 구현. 로컬 Ollama 모델."""

from __future__ import annotations

import httpx
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from ollama import ResponseError

from app.query_legacy.ports import GeneratorUnavailable


def unavailable_reason(error: Exception, *, model: str, timeout_seconds: float) -> str:
    """QRY-R013 모델 서버 장애를 사용자가 무엇을 고칠지 알 수 있는 사유로 옮긴다."""
    if isinstance(error, httpx.TimeoutException):
        return (
            f"모델 응답이 {timeout_seconds:g}초를 넘었습니다. 더 작은 모델을 쓰거나, "
            "Mac 이면 Docker 대신 호스트의 Ollama 를 쓰세요."
        )
    if isinstance(error, ResponseError):
        return (
            f"모델 서버가 오류를 돌려줬습니다 ({model}): {error.error}. "
            "모델을 받았는지 확인하세요 (ollama pull)."
        )
    return f"모델 서버에 연결할 수 없습니다. Ollama 가 떠 있는지 확인하세요. ({error})"


class OllamaSqlGenerator:
    def __init__(self, *, base_url: str, model: str, timeout_seconds: float) -> None:
        self._model = model
        self._timeout = timeout_seconds
        self._chat = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0,  # 같은 질문에 같은 SQL — 평가 결과가 흔들리지 않게
            format="json",  # QRY-R010 출력 형식을 서버 쪽에서도 강제한다
            num_predict=512,
            client_kwargs={"timeout": timeout_seconds},
        )

    async def generate(self, prompt: str) -> str:
        try:
            message = await self._chat.ainvoke([HumanMessage(content=prompt)])
        except (ConnectionError, httpx.HTTPError, ResponseError) as error:
            reason = unavailable_reason(error, model=self._model, timeout_seconds=self._timeout)
            raise GeneratorUnavailable(reason) from error
        content = message.content
        return content if isinstance(content, str) else str(content)
