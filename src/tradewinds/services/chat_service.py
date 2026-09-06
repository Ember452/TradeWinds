"""对话服务:会话 CRUD、消息持久化、SSE 对话(ChatService)。

事件序:citations 先行 → delta* → done;循环与持久化在独立任务中完成,
客户端中途断连时回答/引用/用量仍完整落库(study 08)。
"""

import asyncio
import re
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.agents.orchestrator.llm import Message, Role
from tradewinds.agents.orchestrator.loop import LoopResult, ToolLoop, ToolTrace
from tradewinds.agents.orchestrator.metering import UsageRecorder
from tradewinds.agents.orchestrator.sse import SSEEvent
from tradewinds.core.exceptions import NotFoundError, TradeWindsError
from tradewinds.models.conversation import Conversation, MessageRole
from tradewinds.models.conversation import Message as MessageModel
from tradewinds.models.user import User
from tradewinds.services.rag_service import set_rag_user

_CITATION_URL_PATTERN = re.compile(r"https?://[^\s)\"'>\]]+")
_DELTA_CHUNK_CHARS = 80
_LIMIT_NOTE = "\n\n(说明:受单轮工具调用次数或总时长限制,以上回答基于已获取的部分信息。)"


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

    async def history(self, conversation_id: int, *, limit: int = 20) -> list[MessageModel]:
        result = await self._session.scalars(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.id.desc())
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
    ) -> MessageModel:
        message = MessageModel(
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


def extract_citations(
    tool_trace: Sequence[dict[str, Any] | ToolTrace],
) -> list[dict[str, Any]]:
    """从工具轨迹的返回文本中提取 URL,去重后编号为引用列表。"""
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for trace in tool_trace:
        data = trace if isinstance(trace, dict) else trace.model_dump()
        text = str(data.get("result") or "")
        for url in _CITATION_URL_PATTERN.findall(text):
            url = url.rstrip(".,;")
            if url in seen:
                continue
            seen.add(url)
            citations.append({"index": len(citations) + 1, "url": url})
    return citations


def chunk_text(text: str, size: int = _DELTA_CHUNK_CHARS) -> list[str]:
    """把完整回答切成 delta 片段;SSE 层先发 citations 再发 delta。"""
    return [text[i : i + size] for i in range(0, len(text), size)]


class UserConcurrencyLimiter:
    """每用户并发对话数限流(进程内实现,单 api 容器 MVP)。"""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._counts: dict[int, int] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def slot(self, user_id: int) -> AsyncIterator[None]:
        async with self._lock:
            current = self._counts.get(user_id, 0)
            if current >= self._limit:
                raise TradeWindsError(
                    f"并发对话数已达上限({self._limit})", code="chat_busy", status_code=429
                )
            self._counts[user_id] = current + 1
        try:
            yield
        finally:
            async with self._lock:
                self._counts[user_id] -= 1
                if self._counts[user_id] <= 0:
                    del self._counts[user_id]


class ChatService:
    """对话研究:工具循环 + 引用/轨迹持久化 + SSE 事件流。"""

    def __init__(
        self,
        session: AsyncSession,
        tool_loop: ToolLoop,
        *,
        system_prompt: str,
        recorder: UsageRecorder | None = None,
        limiter: UserConcurrencyLimiter | None = None,
    ) -> None:
        self._conversations = ConversationService(session)
        self._tool_loop = tool_loop
        self._system_prompt = system_prompt
        self._recorder = recorder
        self._limiter = limiter

    async def ensure_conversation(self, user_id: int, conversation_id: int) -> None:
        """归属校验前置:在 SSE 响应开始前完成 404 判定,避免流中途抛错无法回写状态码。"""
        await self._conversations.get(user_id, conversation_id)

    async def stream_with_limit(
        self, user_id: int, conversation_id: int, content: str
    ) -> AsyncIterator[SSEEvent]:
        """路由层入口:并发限流贯穿整个对话期(含工具循环)。"""
        if self._limiter is None:
            async for event in self._respond(user_id, conversation_id, content):
                yield event
            return
        async with self._limiter.slot(user_id):
            async for event in self._respond(user_id, conversation_id, content):
                yield event

    async def _respond(
        self, user_id: int, conversation_id: int, content: str
    ) -> AsyncIterator[SSEEvent]:
        conversation = await self._conversations.get(user_id, conversation_id)
        await self._conversations.add_message(
            conversation.id, role=MessageRole.user, content=content
        )

        history = await self._conversations.history(conversation.id)
        messages = [Message(role=Role.system, content=self._system_prompt)]
        messages += [Message(role=Role(m.role.value), content=m.content) for m in history]

        task = asyncio.create_task(self._run_and_persist(conversation.id, user_id, messages))
        try:
            with set_rag_user(user_id):
                result, citations = await asyncio.shield(task)
        except asyncio.CancelledError:
            # 客户端断连:后台任务继续完成持久化与计量(不丢引用)
            raise

        yield SSEEvent(type="citations", data={"citations": citations})

        answer = result.content
        if result.stopped_reason != "completed":
            answer += _LIMIT_NOTE
        for chunk in chunk_text(answer):
            yield SSEEvent(type="delta", data={"text": chunk})

        yield SSEEvent(
            type="done",
            data={
                "usage": result.usage.model_dump(),
                "iterations": result.iterations,
                "stopped_reason": result.stopped_reason,
            },
        )

    async def _run_and_persist(
        self, conversation_id: int, user_id: int, messages: list[Message]
    ) -> tuple[LoopResult, list[dict[str, Any]]]:
        result = await self._tool_loop.run(messages)
        citations = extract_citations(result.tool_trace)
        await self._conversations.add_message(
            conversation_id,
            role=MessageRole.assistant,
            content=result.content,
            citations=citations,
            tool_trace=[trace.model_dump() for trace in result.tool_trace],
        )
        if self._recorder is not None:
            await self._recorder.record(user_id, "chat", self._tool_loop.model, result.usage)
        return result, citations
