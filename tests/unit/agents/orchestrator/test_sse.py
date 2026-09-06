"""SSE 事件封装测试:格式化、正常透传、异常转 error 事件(自研风险 ③)。"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from tradewinds.agents.orchestrator.sse import SSEEvent, format_sse, guarded_stream


def _delta(text: str) -> SSEEvent:
    return SSEEvent(type="delta", data={"text": text})


def test_format_sse_shape() -> None:
    rendered = format_sse(_delta("你好"))

    assert rendered.startswith("event: delta\n")
    assert rendered.endswith("\n\n")
    payload = rendered.split("data: ", 1)[1].strip()
    assert json.loads(payload) == {"type": "delta", "data": {"text": "你好"}}


async def _gen_from(
    events: list[SSEEvent], *, raise_at_end: Exception | None = None
) -> AsyncIterator[SSEEvent]:
    for event in events:
        yield event
    if raise_at_end is not None:
        raise raise_at_end


async def _collect(agen: AsyncIterator[Any]) -> list[Any]:
    return [item async for item in agen]


async def test_guarded_stream_passes_events_through() -> None:
    events = [_delta("a"), _delta("b")]

    received = await _collect(guarded_stream(_gen_from(events)))

    assert received == events


async def test_generator_error_becomes_error_event_not_silent_drop() -> None:
    received = await _collect(
        guarded_stream(_gen_from([_delta("x")], raise_at_end=RuntimeError("炸了")))
    )

    assert received[0] == _delta("x")
    assert len(received) == 2
    assert received[1].type == "error"
    assert "炸了" in received[1].data["message"]


async def test_cancelled_error_propagates() -> None:
    agen = guarded_stream(_gen_from([], raise_at_end=asyncio.CancelledError()))

    with pytest.raises(asyncio.CancelledError):
        await _collect(agen)


async def test_done_event_has_type_done() -> None:
    done = SSEEvent(type="done", data={"usage": {"total_tokens": 5}})

    assert done.type == "done"
    assert "usage" in done.data
