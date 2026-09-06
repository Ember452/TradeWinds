"""已读内容检索(RAG):用户条目的向量化与语义查询。

范围限定:只检索当前用户自己的 accepted 条目(主题归属隔离),
"我上周看过的那篇讲 xx 的文章"类问题的底层实现。
"""

import contextvars
import json
from contextlib import AbstractContextManager
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.agents.orchestrator.embeddings import Embedder

logger = structlog.get_logger(__name__)

# 对话工具在 ToolLoop 任务内执行,拿不到请求依赖;当前用户经 contextvar 传递
_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "rag_current_user_id", default=None
)


def set_rag_user(user_id: int) -> AbstractContextManager[None]:
    """在对话请求期间声明当前用户;返回可 with 的重置句柄。"""
    token = _current_user_id.set(user_id)

    class _Reset(AbstractContextManager[None]):
        def __exit__(self, *args: object) -> None:
            _current_user_id.reset(token)

    return _Reset()


def current_rag_user() -> int | None:
    return _current_user_id.get()


async def upsert_item_embedding(
    session: AsyncSession, item_id: int, embedder: Embedder, embedding_text: str
) -> bool:
    """生成并写入单条嵌入;失败返回 False(调用方记 warning,不阻塞管道)。"""
    try:
        vector = await embedder.embed(embedding_text)
    except Exception as exc:
        logger.warning("item_embedding_failed", item_id=item_id, error=str(exc))
        return False

    # pgvector 文本字面量 '[1,2,3]';嵌入服务返回浮点列表
    upsert_sql = (
        "INSERT INTO item_embeddings (item_id, embedding, model) "
        "VALUES (:item_id, CAST(:vector AS vector), :model) "
        "ON CONFLICT (item_id) DO UPDATE "
        "SET embedding = EXCLUDED.embedding, model = EXCLUDED.model"
    )
    await session.execute(
        text(upsert_sql),
        {"item_id": item_id, "vector": json.dumps(vector), "model": embedder.model},
    )
    return True


async def search_user_items(
    session: AsyncSession,
    embedder: Embedder,
    user_id: int,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """对当前用户的 accepted 条目做余弦相似度检索,返回按距离升序的条目。"""
    query_vector = await embedder.embed(query)
    rows = await session.execute(
        text(
            "SELECT i.id, i.url, i.title, i.summary, i.source, i.score, i.published_at,"
            " (e.embedding <=> CAST(:qv AS vector)) AS distance"
            " FROM item_embeddings e"
            " JOIN items i ON i.id = e.item_id"
            " JOIN topics t ON t.id = i.topic_id"
            " WHERE t.user_id = :user_id AND i.status = 'accepted'"
            " ORDER BY distance LIMIT :limit"
        ),
        {"qv": json.dumps(query_vector), "user_id": user_id, "limit": limit},
    )
    results = []
    for row in rows.mappings():
        result = dict(row)
        result["distance"] = float(result["distance"])
        results.append(result)
    logger.debug("rag_search", user_id=user_id, query_len=len(query), hits=len(results))
    return results
