"""SqlGenerator 구현. 로컬 Ollama 모델."""

from __future__ import annotations

import httpx
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from ollama import ResponseError

from app.query.ports import GeneratorUnavailable


class OllamaSqlGenerator:
    def __init__(self, *, base_url: str, model: str, timeout_seconds: float) -> None:
        self._model = model
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
        except (ConnectionError, httpx.HTTPError) as error:
            raise GeneratorUnavailable(str(error)) from error
        except ResponseError as error:
            # 모델을 아직 받지 않은 경우가 대부분이다. 다시 만들어도 나아지지 않는다.
            raise GeneratorUnavailable(f"{self._model}: {error.error}") from error
        content = message.content
        return content if isinstance(content, str) else str(content)
