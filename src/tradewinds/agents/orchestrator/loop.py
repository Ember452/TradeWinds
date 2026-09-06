"""工具循环:LLM 多轮调用工具直到给出最终答案,带截断/异常回注/上限护栏。

工具调用走结构化输出路径(AssistantTurn),不依赖 SDK 原生 tool_calls,
供应商切换与流式改造都不影响本循环;取舍记录见 docs/study/03。
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from tradewinds.agents.orchestrator.llm import (
    LLMProvider,
    Message,
    ModelTier,
    Role,
    Usage,
)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class AssistantTurn(BaseModel):
    """工具循环中 LLM 单轮的结构化产物:要么给答案,要么发起工具调用。"""

    content: str | None = None
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
    stopped_reason: Literal["completed", "max_iterations", "timeout"]


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
        try:
            async with asyncio.timeout(self._total_timeout):
                return await self._run_inner(messages)
        except TimeoutError:
            return LoopResult(
                content="",
                tool_trace=[],
                iterations=self._max_iterations,
                usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                stopped_reason="timeout",
            )

    async def _run_inner(self, messages: list[Message]) -> LoopResult:
        working = truncate_messages(messages, max_chars=self._max_context_chars)
        tool_trace: list[ToolTrace] = []
        total_usage = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        for iteration in range(1, self._max_iterations + 1):
            result = await self._provider.complete(
                working, model=self._model, response_model=AssistantTurn
            )
            total_usage = _add_usage(total_usage, result.usage)
            assert isinstance(result.content, AssistantTurn)
            turn = result.content

            if not turn.tool_calls:
                return LoopResult(
                    content=turn.content or "",
                    tool_trace=tool_trace,
                    iterations=iteration,
                    usage=total_usage,
                    stopped_reason="completed",
                )

            working = [*working, Message(role=Role.assistant, content=_turn_as_text(turn))]
            for call in turn.tool_calls:
                trace = await self._execute_tool(call)
                tool_trace.append(trace)
                working.append(Message(role=Role.tool, content=_trace_as_text(trace)))

        return LoopResult(
            content=turn.content or "",
            tool_trace=tool_trace,
            iterations=self._max_iterations,
            usage=total_usage,
            stopped_reason="max_iterations",
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


def _turn_as_text(turn: AssistantTurn) -> str:
    calls = [{"name": c.name, "arguments": c.arguments} for c in turn.tool_calls]
    return json.dumps({"tool_calls": calls}, ensure_ascii=False)


def _trace_as_text(trace: ToolTrace) -> str:
    if trace.error is not None:
        return json.dumps({"tool": trace.tool, "error": trace.error}, ensure_ascii=False)
    return json.dumps({"tool": trace.tool, "result": trace.result}, ensure_ascii=False)


def _add_usage(a: Usage, b: Usage) -> Usage:
    return Usage(
        prompt_tokens=a.prompt_tokens + b.prompt_tokens,
        completion_tokens=a.completion_tokens + b.completion_tokens,
        total_tokens=a.total_tokens + b.total_tokens,
    )
