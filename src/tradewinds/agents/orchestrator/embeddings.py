"""嵌入客户端:OpenAI-compatible /embeddings,用于已读内容向量化。"""

from typing import Any, Protocol

import openai

from tradewinds.core.exceptions import LLMError


class Embedder(Protocol):
    """嵌入生成协议;错误一律包装为 LLMError,调用方按降级处理。"""

    model: str

    async def embed(self, text: str) -> list[float]: ...


class OpenAICompatibleEmbedder:
    def __init__(
        self, *, base_url: str, api_key: str, model: str, client: Any | None = None
    ) -> None:
        self.model = model
        self._client = (
            client if client is not None else openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        )

    async def embed(self, text: str) -> list[float]:
        try:
            response = await self._client.embeddings.create(
                model=self.model, input=[text], encoding_format="float"
            )
        except openai.OpenAIError as exc:
            raise LLMError(f"嵌入生成失败:{exc}") from exc
        return [float(v) for v in response.data[0].embedding]


class DisabledEmbedder:
    """功能关闭时的空实现:调用即报错,由调用方提前判断跳过。"""

    model = "disabled"

    async def embed(self, text: str) -> list[float]:  # pragma: no cover
        raise LLMError("嵌入功能未启用")
