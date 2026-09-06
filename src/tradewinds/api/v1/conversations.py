"""会话路由:CRUD(消息端点见 4.2 SSE 对话)。"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.api.deps import get_current_user, get_db
from tradewinds.models.conversation import Message, MessageRole
from tradewinds.models.user import User
from tradewinds.services.chat_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationRead(BaseModel):
    id: int
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageRead(BaseModel):
    id: int
    role: MessageRole
    content: str
    citations: list[dict[str, Any]] | None
    tool_trace: list[dict[str, Any]] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]


def _service(session: AsyncSession = Depends(get_db)) -> ConversationService:
    return ConversationService(session)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_service),
) -> ConversationRead:
    conversation = await service.create(current_user, title=payload.title)
    return ConversationRead.model_validate(conversation)


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_service),
) -> list[ConversationRead]:
    return [ConversationRead.model_validate(c) for c in await service.list_all(current_user.id)]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_service),
) -> ConversationDetail:
    conversation = await service.get(current_user.id, conversation_id)
    messages: list[Message] = await service.history(conversation_id, limit=200)
    detail = ConversationDetail.model_validate(conversation)
    detail.messages = [MessageRead.model_validate(m) for m in messages]
    return detail


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_service),
) -> dict[str, str]:
    await service.delete(current_user.id, conversation_id)
    return {"message": "已删除"}
