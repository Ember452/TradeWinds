"""工具循环:LLM 多轮调用工具直到给出最终答案,带截断/异常回注/上限护栏。

两阶段设计:每轮先走结构化输出决策(LoopDecision,不依赖 SDK 原生 tool_calls,
供应商切换不影响本循环),决策为空 tool_calls 表示信息足够;作答走 provider
流式输出,文本增量以事件透出给调用方。取舍记录见 docs/study/03 与 19。
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from tradewinds.agents.orchestrator.llm import (
    LLMProvider,
    Message,
    ModelTier,
    Role,
    Usage,
)
from tradewinds.core.exceptions import LLMError


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class LoopDecision(BaseModel):
    """决策轮结构化产物:tool_calls 非空=要调工具;空=信息足够,请求作答。"""

    tool_calls: list[ToolCallRequest] = []


class Tool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    execute: Callable[[dict[str, Any]], Awaitable[str]]


class ToolTrace(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}
    result: str | None = None
    error: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self, *, name: str, description: str, execute: Callable[[dict[str, Any]], Awaitable[str]]
    ) -> None:
        self._tools[name] = Tool(name=name, description=description, execute=execute)

    def names(self) -> list[str]:
        return list(self._tools)

    def describe(self) -> str:
        """渲染工具清单,供系统 prompt 注入。"""
        lines = [f"- {tool.name}: {tool.description}" for tool in self._tools.values()]
        return "\n".join(lines)

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools[name]  # KeyError 由循环层转为错误回注
        return await tool.execute(arguments)


class LoopResult(BaseModel):
    content: str
    tool_trace: list[ToolTrace] = []
    iterations: int
    usage: Usage
    stopped_reason: Literal["completed", "max_iterations", "timeout", "stream_interrupted"]


class ToolTraceEvent(BaseModel):
    """单次工具执行完成(成功或错误回注)。"""

    trace: ToolTrace


class AnswerDeltaEvent(BaseModel):
    """最终回答的文本增量。"""

    text: str


class LoopDoneEvent(BaseModel):
    """循环结束:result 为完整产物(含聚合 usage 与 stopped_reason)。"""

    result: LoopResult


LoopEvent = ToolTraceEvent | AnswerDeltaEvent | LoopDoneEvent


_ANSWER_INSTRUCTION = (
    "检索结束。请基于以上工具结果撰写最终回答:中文 Markdown,先结论后依据,"
    "按系统提示中的引用规范在句末标注 [编号];不要输出 JSON。"
)


def _zero_usage() -> Usage:
    return Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)


@dataclass
class _LoopState:
    """跨事件累积的循环状态:超时/中断时已产出内容不丢弃。"""

    tool_trace: list[ToolTrace] = field(default_factory=list)
    answer_parts: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=_zero_usage)

    def add_usage(self, usage: Usage) -> None:
        self.usage = Usage(
            prompt_tokens=self.usage.prompt_tokens + usage.prompt_tokens,
            completion_tokens=self.usage.completion_tokens + usage.completion_tokens,
            total_tokens=self.usage.total_tokens + usage.total_tokens,
        )


def truncate_messages(messages: list[Message], *, max_chars: int) -> list[Message]:
    """超长截断:保留系统指令 + 从最新往前保留消息(自然涵盖最近的工具结果)。"""
    total = sum(len(m.content) for m in messages)
    if total <= max_chars:
        return messages

    system = [m for m in messages if m.role is Role.system]
    rest = [m for m in messages if m.role is not Role.system]
    budget = max_chars - sum(len(m.content) for m in system)

    kept: list[Message] = []
    used = 0
    for message in reversed(rest):
        if used + len(message.content) > budget:
            break
        kept.append(message)
        used += len(message.content)
    return system + list(reversed(kept))


class ToolLoop:
    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        *,
        model: ModelTier = ModelTier.low,
        max_iterations: int = 10,
        total_timeout: float = 120.0,
        max_context_chars: int = 24_000,
    ) -> None:
        self._provider = provider
        self._tools = tools
        self._model = model
        self._max_iterations = max_iterations
        self._total_timeout = total_timeout
        self._max_context_chars = max_context_chars

    @property
    def model(self) -> ModelTier:
        return self._model

    async def run(self, messages: list[Message]) -> LoopResult:
        """非流式入口:消费 run_streaming,只取最终结果。"""
        result: LoopResult | None = None
        async for event in self.run_streaming(messages):
            if isinstance(event, LoopDoneEvent):
                result = event.result
        assert result is not None  # run_streaming 保证以 LoopDoneEvent 结束
        return result

    async def run_streaming(self, messages: list[Message]) -> AsyncIterator[LoopEvent]:
        """流式入口:工具轨迹事件 → 作答增量事件 → 结束事件。"""
        state = _LoopState()
        try:
            async with asyncio.timeout(self._total_timeout):
                async for event in self._run_inner_streaming(messages, state):
                    yield event
        except TimeoutError:
            yield LoopDoneEvent(
                result=LoopResult(
                    content="".join(state.answer_parts),
                    tool_trace=state.tool_trace,
                    iterations=self._max_iterations,
                    usage=state.usage,
                    stopped_reason="timeout",
                )
            )

    async def _run_inner_streaming(
        self, messages: list[Message], state: _LoopState
    ) -> AsyncIterator[LoopEvent]:
        working = truncate_messages(messages, max_chars=self._max_context_chars)

        iterations = 0
        for _ in range(self._max_iterations):
            iterations += 1
            result = await self._provider.complete(
                working, model=self._model, response_model=LoopDecision
            )
            state.add_usage(result.usage)
            decision = result.content
            assert isinstance(decision, LoopDecision)

            if not decision.tool_calls:
                break

            working = [*working, Message(role=Role.assistant, content=_decision_as_text(decision))]
            for call in decision.tool_calls:
                trace = await self._execute_tool(call)
                state.tool_trace.append(trace)
                working.append(Message(role=Role.tool, content=_trace_as_text(trace)))
                yield ToolTraceEvent(trace=trace)
        else:
            yield LoopDoneEvent(
                result=LoopResult(
                    content="",
                    tool_trace=state.tool_trace,
                    iterations=self._max_iterations,
                    usage=state.usage,
                    stopped_reason="max_iterations",
                )
            )
            return

        answer_messages = [*working, Message(role=Role.user, content=_ANSWER_INSTRUCTION)]
        try:
            async for event in self._provider.stream(answer_messages, model=self._model):
                if event.delta:
                    state.answer_parts.append(event.delta)
                    yield AnswerDeltaEvent(text=event.delta)
                if event.usage is not None:
                    state.add_usage(event.usage)
        except LLMError:
            # 已发出的增量无法撤回:有半截回答就以"流中断"收尾,否则上抛由调用方报错
            if not state.answer_parts:
                raise
            yield LoopDoneEvent(
                result=LoopResult(
                    content="".join(state.answer_parts),
                    tool_trace=state.tool_trace,
                    iterations=iterations,
                    usage=state.usage,
                    stopped_reason="stream_interrupted",
                )
            )
            return

        yield LoopDoneEvent(
            result=LoopResult(
                content="".join(state.answer_parts),
                tool_trace=state.tool_trace,
                iterations=iterations,
                usage=state.usage,
                stopped_reason="completed",
            )
        )

    async def _execute_tool(self, call: ToolCallRequest) -> ToolTrace:
        try:
            output = await self._tools.call(call.name, call.arguments)
        except KeyError:
            return ToolTrace(
                tool=call.name, arguments=call.arguments, error=f"未知工具:{call.name}"
            )
        except Exception as exc:  # 工具失败不中断循环,错误作为结果回注模型(自研风险 ②)
            return ToolTrace(tool=call.name, arguments=call.arguments, error=str(exc))
        return ToolTrace(tool=call.name, arguments=call.arguments, result=output)


def _decision_as_text(decision: LoopDecision) -> str:
    calls = [{"name": c.name, "arguments": c.arguments} for c in decision.tool_calls]
    return json.dumps({"tool_calls": calls}, ensure_ascii=False)


def _trace_as_text(trace: ToolTrace) -> str:
    if trace.error is not None:
        return json.dumps({"tool": trace.tool, "error": trace.error}, ensure_ascii=False)
    return json.dumps({"tool": trace.tool, "result": trace.result}, ensure_ascii=False)
