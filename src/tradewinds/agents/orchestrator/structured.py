"""结构化输出执行器:校验失败把校验错误回注模型重试,上限 2 次。"""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from tradewinds.agents.orchestrator.llm import LLMProvider, Message, ModelTier, Role
from tradewinds.core.exceptions import LLMError

T = TypeVar("T", bound=BaseModel)

_MAX_RETRIES = 2


class StructuredRunner:
    """把"LLM 输出必须符合 schema"从一次性尝试变成带反馈的重试循环。"""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def run(self, prompt: str, response_model: type[T], *, model: ModelTier) -> T:
        """返回经 response_model 校验的实例;校验失败最多重试 2 次后抛 LLMError。"""
        messages = [Message(role=Role.user, content=prompt)]

        for attempt in range(1 + _MAX_RETRIES):
            result = await self._provider.complete(
                messages, model=model, response_model=response_model
            )
            content = result.content
            if isinstance(content, response_model):
                return content
            # 供应商未走结构化解析路径时自行校验
            try:
                return response_model.model_validate(content)
            except ValidationError as exc:
                if attempt == _MAX_RETRIES:
                    raise LLMError(f"结构化输出校验失败(已重试 {_MAX_RETRIES} 次):{exc}") from exc
                feedback = f"你的输出不符合 schema,请修正后重新输出完整 JSON。错误:{exc}"
                messages.append(Message(role=Role.assistant, content=str(content)))
                messages.append(Message(role=Role.user, content=feedback))

        raise LLMError("结构化输出校验失败")  # pragma: no cover —— 循环必在此前 return/raise
