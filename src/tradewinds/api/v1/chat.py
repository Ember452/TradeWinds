"""对话路由:SSE 消息端点(事件流 text/event-stream)。"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from tradewinds.agents.orchestrator.sse import format_sse
from tradewinds.api.deps import get_chat_service, get_current_user
from tradewinds.models.user import User
from tradewinds.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """发送消息,SSE 流式返回:citations → delta* → done。"""

    async def event_stream() -> AsyncIterator[str]:
        async for event in chat_service.stream_with_limit(
            current_user.id, conversation_id, payload.content
        ):
            yield format_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
