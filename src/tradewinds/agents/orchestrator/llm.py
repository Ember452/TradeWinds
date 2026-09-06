"""LLM 供应商抽象:OpenAI-compatible SDK,型号全部来自配置,代码不出现型号字符串。

架构契约(architecture.md 第 5 节):
    complete(messages, model=ModelTier, response_model=None) -> LLMResult[T]
    stream(messages, model=ModelTier) -> AsyncIterator[StreamEvent]
"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from enum import StrEnum
from typing import Any, Protocol

import openai
from pydantic import BaseModel

from tradewinds.core.exceptions import LLMError


class ModelTier(StrEnum):
    """模型分档:low 给打分/检索类角色,mid 给摘要/对话。"""

    low = "low"
    mid = "mid"


class Role(StrEnum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Message(BaseModel):
    role: Role
    content: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResult(BaseModel):
    """一次 LLM 调用的产物:内容 + 用量。content 为 str 或 response_model 实例。"""

    content: Any
    usage: Usage


class StreamEvent(BaseModel):
    """流式事件:delta 为文本增量;usage 仅出现在最后一个事件(供应商支持时)。

    供应商不支持 stream_options.include_usage 时 usage 为 None,调用方按 0 计量。
    """

    delta: str = ""
    usage: Usage | None = None


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        *,
        model: ModelTier,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResult: ...

    def stream(
        self, messages: list[Message], *, model: ModelTier
    ) -> AsyncIterator[StreamEvent]: ...


_RETRYABLE = (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError)
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0


def _message_dicts(messages: list[Message]) -> list[dict[str, str]]:
    return [{"role": message.role.value, "content": message.content} for message in messages]


def _usage_of(raw_usage: Any) -> Usage:
    return Usage(
        prompt_tokens=raw_usage.prompt_tokens,
        completion_tokens=raw_usage.completion_tokens,
        total_tokens=raw_usage.prompt_tokens + raw_usage.completion_tokens,
    )


class OpenAICompatibleProvider:
    """默认实现。429/连接错误/5xx 按指数退避重试(上限 3 次),耗尽抛 LLMError。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_map: Mapping[ModelTier, str],
        client: Any | None = None,
    ) -> None:
        self._model_map = dict(model_map)
        if client is not None:
            self._client = client
        else:
            self._client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0)

    def _model_name(self, tier: ModelTier) -> str:
        try:
            return self._model_map[tier]
        except KeyError as exc:
            raise LLMError(f"未配置 {tier.value} 档位模型") from exc

    async def complete(
        self,
        messages: list[Message],
        *,
        model: ModelTier,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResult:
        model_name = self._model_name(model)
        last_error: Exception | None = None

        for attempt in range(1 + _MAX_RETRIES):
            try:
                if response_model is None:
                    raw = await self._client.chat.completions.create(
                        model=model_name, messages=_message_dicts(messages)
                    )
                    return LLMResult(
                        content=raw.choices[0].message.content, usage=_usage_of(raw.usage)
                    )
                raw = await self._client.beta.chat.completions.parse(
                    model=model_name,
                    messages=_message_dicts(messages),
                    response_model=response_model,
                )
                return LLMResult(content=raw.parsed, usage=_usage_of(raw.usage))
            except _RETRYABLE as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
            except openai.OpenAIError as exc:
                # 参数/鉴权等不可重试错误,立即包装为统一异常
                raise LLMError(f"LLM 调用失败:{exc}") from exc

        raise LLMError(f"LLM 调用失败(已重试 {_MAX_RETRIES} 次):{last_error}")

    async def stream(
        self, messages: list[Message], *, model: ModelTier
    ) -> AsyncIterator[StreamEvent]:
        """流式输出文本增量,最后一个事件尽量带 usage。

        流中途失败不重试(已发出的增量无法撤回);供应商不认
        stream_options 时去掉该参数重试一次,代价是拿不到 usage。
        """
        model_name = self._model_name(model)
        try:
            raw_stream = await self._client.chat.completions.create(
                model=model_name,
                messages=_message_dicts(messages),
                stream=True,
                stream_options={"include_usage": True},
            )
        except openai.BadRequestError:
            raw_stream = await self._client.chat.completions.create(
                model=model_name, messages=_message_dicts(messages), stream=True
            )
        async for chunk in raw_stream:
            if not chunk.choices:
                # include_usage 的收尾块只带 usage,无 choices
                if chunk.usage is not None:
                    yield StreamEvent(usage=_usage_of(chunk.usage))
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield StreamEvent(delta=delta)
