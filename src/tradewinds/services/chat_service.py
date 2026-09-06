"""对话服务:会话 CRUD、消息持久化、SSE 对话(ChatService,Task 4.2)。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.exceptions import NotFoundError
from tradewinds.models.conversation import Conversation, Message, MessageRole
from tradewinds.models.user import User


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User, *, title: str) -> Conversation:
        conversation = Conversation(user_id=user.id, title=title)
        self._session.add(conversation)
        await self._session.commit()
        await self._session.refresh(conversation)
        return conversation

    async def get(self, user_id: int, conversation_id: int) -> Conversation:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None or conversation.user_id != user_id:
            raise NotFoundError("会话不存在")
        return conversation

    async def list_all(self, user_id: int) -> list[Conversation]:
        result = await self._session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result)

    async def delete(self, user_id: int, conversation_id: int) -> None:
        conversation = await self.get(user_id, conversation_id)
        await self._session.delete(conversation)
        await self._session.commit()

    async def history(self, conversation_id: int, *, limit: int = 20) -> list[Message]:
        result = await self._session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        return list(reversed(result.all()))

    async def add_message(
        self,
        conversation_id: int,
        *,
        role: MessageRole,
        content: str,
        citations: list[dict[str, Any]] | None = None,
        tool_trace: list[dict[str, Any]] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            tool_trace=tool_trace,
        )
        self._session.add(message)
        await self._session.commit()
        await self._session.refresh(message)
        return message
