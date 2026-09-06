"""ToolLoop 测试:两阶段循环(决策+流式作答)、异常回注、上下文截断、迭代上限。

对应实施计划 Task 2.3 的三条自研风险与 2026-09 流式改造(docs/plans/
2026-09-06-agent-experience-upgrade.md Task A),各有专项用例。
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from tradewinds.agents.orchestrator.llm import (
    LLMResult,
    Message,
    ModelTier,
    Role,
    StreamEvent,
    Usage,
)
from tradewinds.agents.orchestrator.loop import (
    AnswerDeltaEvent,
    LoopDecision,
    LoopDoneEvent,
    ToolCallRequest,
    ToolLoop,
    ToolRegistry,
    ToolTraceEvent,
    truncate_messages,
)
from tradewinds.core.exceptions import LLMError

_USAGE_CALL = Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
_USAGE_STREAM = Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10)


class FakeProvider:
    """决策轮返回预置 LoopDecision;作答轮按预置增量流式输出。"""

    def __init__(
        self,
        decisions: list[LoopDecision],
        *,
        deltas: list[str] | None = None,
        stream_usage: Usage | None = None,
        stream_error: Exception | None = None,
        stream_delay: float = 0.0,
    ) -> None:
        self._decisions = list(decisions)
        self._deltas = deltas or []
        self._stream_usage = stream_usage
        self._stream_error = stream_error
        self._stream_delay = stream_delay
        self.decision_calls: list[list[Message]] = []
        self.stream_calls: list[list[Message]] = []

    async def complete(self, messages: list[Message], **kwargs: Any) -> LLMResult:
        self.decision_calls.append(messages)
        return LLMResult(content=self._decisions.pop(0), usage=_USAGE_CALL)

    async def stream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[StreamEvent]:
        self.stream_calls.append(messages)
        for index, delta in enumerate(self._deltas):
            if self._stream_delay and index > 0:  # 首个增量立即到达,模拟中途停顿
                await asyncio.sleep(self._stream_delay)
            yield StreamEvent(delta=delta)
        if self._stream_error is not None:
            raise self._stream_error
        if self._stream_usage is not None:
            yield StreamEvent(usage=self._stream_usage)


def _registry() -> ToolRegistry:
    registry = ToolRegistry()

    async def search(arguments: dict[str, Any]) -> str:
        return f"结果:{arguments['query']}"

    registry.register(name="search_web", description="搜索", execute=search)
    return registry


def _answer_call(messages: list[Message]) -> Message:
    """作答轮的收尾指令消息,断言循环在作答前追加了它。"""
    return messages[-1]


# --- 基础循环 ---


async def test_no_tool_decision_streams_answer() -> None:
    provider = FakeProvider(
        [LoopDecision(tool_calls=[])],
        deltas=["你好", "答案"],
        stream_usage=_USAGE_STREAM,
    )
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)

    events = [event async for event in loop.run_streaming([Message(role=Role.user, content="q")])]
    deltas = [e.text for e in events if isinstance(e, AnswerDeltaEvent)]
    done = next(e for e in events if isinstance(e, LoopDoneEvent)).result

    assert deltas == ["你好", "答案"]
    assert done.content == "你好答案"
    assert done.stopped_reason == "completed"
    assert done.iterations == 1
    # usage 聚合:决策轮 + 作答流
    assert done.usage == Usage(prompt_tokens=6, completion_tokens=6, total_tokens=12)
    # 作答前追加了作答指令消息
    assert "最终回答" in _answer_call(provider.stream_calls[0]).content


async def test_run_matches_run_streaming_result() -> None:
    provider = FakeProvider([LoopDecision(tool_calls=[])], deltas=["答案"])
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)
    messages = [Message(role=Role.user, content="q")]

    result = await loop.run(messages)

    assert result.content == "答案"
    assert result.stopped_reason == "completed"


async def test_tool_call_is_executed_and_result_fed_back() -> None:
    provider = FakeProvider(
        [
            LoopDecision(
                tool_calls=[ToolCallRequest(name="search_web", arguments={"query": "AI"})]
            ),
            LoopDecision(tool_calls=[]),
        ],
        deltas=["完成"],
    )
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)

    events = [event async for event in loop.run_streaming([Message(role=Role.user, content="q")])]
    traces = [e.trace for e in events if isinstance(e, ToolTraceEvent)]
    deltas = [e for e in events if isinstance(e, AnswerDeltaEvent)]
    done = next(e for e in events if isinstance(e, LoopDoneEvent)).result

    # 事件序:工具轨迹先于作答增量
    assert traces and deltas
    assert events.index(ToolTraceEvent(trace=traces[0])) < events.index(deltas[0])
    assert done.tool_trace[0].result == "结果:AI"
    assert done.iterations == 2
    # 第二次决策调用的消息包含工具结果(role=tool)
    tool_messages = [m for m in provider.decision_calls[1] if m.role is Role.tool]
    assert tool_messages and "结果:AI" in tool_messages[0].content


async def test_unknown_tool_returns_error_string_to_model() -> None:
    provider = FakeProvider(
        [
            LoopDecision(tool_calls=[ToolCallRequest(name="no_such_tool")]),
            LoopDecision(tool_calls=[]),
        ],
        deltas=["好"],
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
            LoopDecision(tool_calls=[ToolCallRequest(name="fragile")]),
            LoopDecision(tool_calls=[]),
        ],
        deltas=["降级作答"],
    )
    loop = ToolLoop(provider, registry, model=ModelTier.mid)

    result = await loop.run([Message(role=Role.user, content="x")])

    assert result.content == "降级作答"
    assert result.tool_trace[0].error == "源站超时"
    tool_messages = [m for m in provider.decision_calls[1] if m.role is Role.tool]
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
    provider = FakeProvider([LoopDecision(tool_calls=[])], deltas=["ok"])
    loop = ToolLoop(provider, _registry(), model=ModelTier.low, max_context_chars=300)
    messages = [Message(role=Role.system, content="sys")]
    messages += [Message(role=Role.user, content="filler " + "y" * 200) for _ in range(10)]
    messages.append(Message(role=Role.user, content="question"))

    await loop.run(messages)

    sent = provider.decision_calls[0]
    assert len(sent) < len(messages)
    assert sent[0].content == "sys"
    assert sent[-1].content == "question"  # 作答指令只在作答轮追加


# --- 迭代与超时上限 ---


async def test_max_iterations_stops_loop() -> None:
    always_tool = LoopDecision(
        tool_calls=[ToolCallRequest(name="search_web", arguments={"query": "q"})]
    )
    provider = FakeProvider([always_tool] * 10)
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid, max_iterations=3)

    result = await loop.run([Message(role=Role.user, content="x")])

    assert result.stopped_reason == "max_iterations"
    assert result.iterations == 3
    assert result.content == ""


async def test_timeout_preserves_partial_answer() -> None:
    provider = FakeProvider(
        [LoopDecision(tool_calls=[])],
        deltas=["部分", "未完"],
        stream_delay=10.0,
    )
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid, total_timeout=0.05)

    result = await loop.run([Message(role=Role.user, content="x")])

    assert result.stopped_reason == "timeout"
    assert result.content == "部分"


# --- 作答流中断:已发出的增量不撤回 ---


async def test_stream_error_with_partial_answer_returns_interrupted() -> None:
    provider = FakeProvider(
        [LoopDecision(tool_calls=[])],
        deltas=["半截"],
        stream_error=LLMError("供应商断流"),
    )
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)

    result = await loop.run([Message(role=Role.user, content="x")])

    assert result.stopped_reason == "stream_interrupted"
    assert result.content == "半截"


async def test_stream_error_without_answer_propagates() -> None:
    provider = FakeProvider([LoopDecision(tool_calls=[])], stream_error=LLMError("连接失败"))
    loop = ToolLoop(provider, _registry(), model=ModelTier.mid)

    with pytest.raises(LLMError):
        await loop.run([Message(role=Role.user, content="x")])


# --- 未知工具在注册表层即报错,由循环层转成错误回注 ---


async def test_registry_call_unknown_tool_raises_key_error() -> None:
    registry = _registry()

    with pytest.raises(KeyError):
        await registry.call("missing", {})
