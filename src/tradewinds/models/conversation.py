"""conversations 与 messages:对话研究 Agent 的会话与消息。

assistant 消息持久化 citations(编号引用,对应原文链接)与
tool_trace(工具轨迹),支持历史会话完整回看。
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tradewinds.models.base import Base


class MessageRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, native_enum=False, length=16), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 编号引用列表:[{"index": 1, "url": ..., "title": ..., "source": ...}]
    citations: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    # 工具轨迹:[{"tool": ..., "arguments": ..., "result"/"error": ...}]
    tool_trace: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
