"""ToolLoop 测试:工具调用、异常回注、上下文截断、迭代上限。

对应实施计划 Task 2.3 的三条自研风险,各有专项用例。
"""

from typing import Any

import pytest

from tradewinds.agents.orchestrator.llm import LLMResult, Message, ModelTier, Role, Usage
from tradewinds.agents.orchestrator.loop import (
    AssistantTurn,
    ToolLoop,
    ToolRegistry,
    truncate_messages,
)


class FakeProvider:
    def __init__(self, turns: list[AssistantTurn]) -> None:
        self._turns = list(turns)
        self.calls: list[list[Message]] = []

    async def complete(self, messages: list[Message], **kwargs: Any) -> LLMResult:
        self.calls.append(messages)
        turn = self._turns.pop(0)
        usage = Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        return LLMResult(content=turn, usage=usage)

    def stream(self, messages: list[Message], **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


def _registry() -> ToolRegistry:
    registry = ToolRegistry()

    async def search(arguments: dict[str, Any]) -> str:
        return f"结果:{arguments['query']}"

    registry.register(
        name="web_search",
        description="搜索网页",
        execute=search,
    )
    return registry


# --- 基础循环 ---


async def test_no_tool_call_returns_content_immediately() -> None:
    provider = FakeProvider([AssistantTurn(content="最终答案", tool_calls=[])])
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)

    result = await loop.run([Message(role=Role.user, content="问题")])

    assert result.content == "最终答案"
    assert result.stopped_reason == "completed"
    assert result.iterations == 1


async def test_tool_call_is_executed_and_result_fed_back() -> None:
    provider = FakeProvider(
        [
            AssistantTurn(
                tool_calls=[{"name": "web_search", "arguments": {"query": "TradeWinds"}}]
            ),
            AssistantTurn(content="完成"),
        ]
    )
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)

    result = await loop.run([Message(role=Role.user, content="查一下")])

    assert result.content == "完成"
    assert result.iterations == 2
    assert len(result.tool_trace) == 1
    assert result.tool_trace[0].tool == "web_search"
    assert result.tool_trace[0].result == "结果:TradeWinds"
    # 第二次调用的消息包含工具结果(role=tool)
    tool_messages = [m for m in provider.calls[1] if m.role is Role.tool]
    assert tool_messages and "结果:TradeWinds" in tool_messages[0].content


async def test_unknown_tool_returns_error_string_to_model() -> None:
    provider = FakeProvider(
        [
            AssistantTurn(tool_calls=[{"name": "no_such_tool", "arguments": {}}]),
            AssistantTurn(content="好"),
        ]
    )
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)

    result = await loop.run([Message(role=Role.user, content="x")])

    assert result.content == "好"
    assert result.tool_trace[0].error is not None


# --- 自研风险 ②:工具抛异常 → 错误回注模型、循环继续 ---


async def test_tool_exception_becomes_tool_result_and_loop_continues() -> None:
    registry = _registry()

    async def boom(arguments: dict[str, Any]) -> str:
        raise RuntimeError("源站超时")

    registry.register(name="fragile", description="易碎工具", execute=boom)
    provider = FakeProvider(
        [
            AssistantTurn(tool_calls=[{"name": "fragile", "arguments": {}}]),
            AssistantTurn(content="降级作答"),
        ]
    )
    loop = ToolLoop(provider, registry, model=ModelTier.mid)

    result = await loop.run([Message(role=Role.user, content="x")])

    # 循环没有中断,错误作为工具结果回注
    assert result.content == "降级作答"
    assert result.tool_trace[0].error == "源站超时"
    tool_messages = [m for m in provider.calls[1] if m.role is Role.tool]
    assert tool_messages and "源站超时" in tool_messages[0].content


# --- 自研风险 ①:上下文超长按"保系统指令+最近消息"截断 ---


def test_truncate_keeps_system_and_recent_messages() -> None:
    messages = [Message(role=Role.system, content="系统指令" * 10)]
    for i in range(100):
        messages.append(Message(role=Role.user, content=f"历史消息 {i:03d} " + "x" * 50))
    messages.append(Message(role=Role.user, content="最新问题"))

    truncated = truncate_messages(messages, max_chars=600)

    assert truncated[0].content == messages[0].content  # 系统指令保留
    assert truncated[-1].content == "最新问题"  # 最近消息保留
    assert len(truncated) < len(messages)


def test_truncate_noop_when_within_budget() -> None:
    messages = [Message(role=Role.user, content="短消息")]

    assert truncate_messages(messages, max_chars=1000) == messages


async def test_loop_truncates_oversized_context() -> None:
    provider = FakeProvider([AssistantTurn(content="ok")])
    loop = ToolLoop(provider, _registry(), model=ModelTier.low, max_context_chars=300)
    messages = [Message(role=Role.system, content="sys")]
    messages += [Message(role=Role.user, content="filler " + "y" * 200) for _ in range(10)]
    messages.append(Message(role=Role.user, content="question"))

    await loop.run(messages)

    sent = provider.calls[0]
    assert len(sent) < len(messages)
    assert sent[0].content == "sys"
    assert sent[-1].content == "question"


# --- 迭代与超时上限 ---


async def test_max_iterations_stops_loop() -> None:
    always_tool = AssistantTurn(tool_calls=[{"name": "web_search", "arguments": {"query": "q"}}])
    provider = FakeProvider([always_tool] * 10)
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid, max_iterations=3)

    result = await loop.run([Message(role=Role.user, content="x")])

    assert result.stopped_reason == "max_iterations"
    assert result.iterations == 3


async def test_total_timeout_returns_timeout_result() -> None:
    import asyncio

    provider = FakeProvider([AssistantTurn(content="slow")])

    async def slow_complete(messages: list[Message], **kwargs: Any) -> LLMResult:
        await asyncio.sleep(10)
        raise AssertionError("不应执行到这里")  # pragma: no cover

    provider.complete = slow_complete  # type: ignore[method-assign]
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid, total_timeout=0.05)

    result = await loop.run([Message(role=Role.user, content="x")])

    assert result.stopped_reason == "timeout"


# --- 未知工具在注册表层即报错,由循环层转成错误回注 ---


async def test_registry_call_unknown_tool_raises_key_error() -> None:
    registry = _registry()

    with pytest.raises(KeyError):
        await registry.call("missing", {})
