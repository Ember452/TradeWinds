"""StructuredRunner 测试:校验失败把错误回注重试,上限 2 次。"""

from typing import Any

import pytest
from pydantic import BaseModel, field_validator

from tradewinds.agents.orchestrator.llm import LLMResult, Message, ModelTier, Usage
from tradewinds.agents.orchestrator.structured import StructuredRunner
from tradewinds.core.exceptions import LLMError


class FakeProvider:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.calls: list[list[Message]] = []

    async def complete(self, messages: list[Message], **kwargs: Any) -> LLMResult:
        self.calls.append(messages)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def stream(self, messages: list[Message], **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


class Answer(BaseModel):
    number: int


class StrictAnswer(BaseModel):
    number: int

    @field_validator("number")
    @classmethod
    def must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("number 必须为正数")
        return value


def _result(content: Any) -> LLMResult:
    return LLMResult(
        content=content, usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    )


async def test_success_returns_model() -> None:
    provider = FakeProvider([_result(Answer(number=5))])
    runner = StructuredRunner(provider)

    answer = await runner.run("给个数", Answer, model=ModelTier.low)

    assert answer == Answer(number=5)


async def test_validation_error_is_fed_back_and_retried() -> None:
    # 用 dict 模拟 LLM 产出的非法输出(-1 在构造期就会被 pydantic 拒绝)
    provider = FakeProvider([_result({"number": -1}), _result(StrictAnswer(number=3))])
    runner = StructuredRunner(provider)

    answer = await runner.run("给个数", StrictAnswer, model=ModelTier.low)

    assert answer == StrictAnswer(number=3)
    assert len(provider.calls) == 2
    # 第二次调用的消息里应包含校验错误描述
    feedback = provider.calls[1][-1].content
    assert "number 必须为正数" in feedback


async def test_retry_exhausted_raises_llm_error() -> None:
    provider = FakeProvider([_result({"number": -1}) for _ in range(3)])
    runner = StructuredRunner(provider)

    with pytest.raises(LLMError):
        await runner.run("给个数", StrictAnswer, model=ModelTier.low)

    # 首次 + 2 次重试
    assert len(provider.calls) == 3
