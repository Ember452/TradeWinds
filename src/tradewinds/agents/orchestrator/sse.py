"""SSE 事件封装:delta/citations/done/error 四类事件。

guarded_stream 保证生成器中途抛错时客户端收到 error 事件,
而不是连接静默断开(自研风险 ③);客户端主动断连(CancelledError)原样上抛,
由上层决定计量与落库收尾(Task 4.2)。
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel


class SSEEvent(BaseModel):
    type: Literal["delta", "citations", "done", "error"]
    data: dict[str, Any] = {}


def format_sse(event: SSEEvent) -> str:
    """渲染为 text/event-stream 单事件帧。"""
    payload = json.dumps(event.model_dump(), ensure_ascii=False)
    return f"event: {event.type}\ndata: {payload}\n\n"


async def guarded_stream(events: AsyncIterator[SSEEvent]) -> AsyncIterator[SSEEvent]:
    """透传事件流;流内异常转为 error 事件,CancelledError 除外。"""
    try:
        async for event in events:
            yield event
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        yield SSEEvent(type="error", data={"code": "stream_failed", "message": str(exc)})
