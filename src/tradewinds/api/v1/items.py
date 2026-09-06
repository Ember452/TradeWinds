"""Feed 路由:主题条目的增量 keyset 分页读取。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.api.deps import get_current_user, get_db, get_topic_service
from tradewinds.models.user import User
from tradewinds.services.item_service import list_items, record_click
from tradewinds.services.rag_service import search_user_items
from tradewinds.services.topic_service import TopicService

router = APIRouter(tags=["feed"])


class ItemRead(BaseModel):
    id: int
    source: str
    url: str
    title: str
    summary: str | None
    reason: str | None
    score: float | None
    cluster_key: str | None
    published_at: datetime | None

    model_config = {"from_attributes": True}


class FeedPage(BaseModel):
    items: list[ItemRead]
    next_cursor: int | None = None


class SearchHit(BaseModel):
    id: int
    url: str
    title: str
    summary: str | None
    source: str
    score: float | None
    distance: float


@router.get("/items/search")
async def search_own_items(
    request: Request,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SearchHit]:
    """已读内容语义检索:"我上周看过的那篇讲 xx 的文章"。

    嵌入功能未启用(未配置 TRADEWINDS_EMBEDDING_MODEL)→ 404 关闭。
    """
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="检索功能未启用")
    rows = await search_user_items(session, embedder, current_user.id, q, limit=limit)
    return [SearchHit(**row) for row in rows]


@router.post("/items/{item_id}/click", status_code=204)
async def click_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """点击上报(幂等):偏好画像的行为信号。"""
    await record_click(session, current_user.id, item_id)


@router.get("/topics/{topic_id}/items", response_model=FeedPage)
async def list_topic_items(
    topic_id: int,
    cursor: int | None = Query(default=None, description="上一页返回的 next_cursor"),
    min_score: float | None = Query(default=None, ge=0, le=10),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
    session: AsyncSession = Depends(get_db),
) -> FeedPage:
    """keyset 分页(按 id 倒序,禁止 offset 深翻页);默认仅 accepted 条目可见。

    跨用户访问 404,不泄露存在性。
    """
    await topic_service.get(current_user.id, topic_id)
    rows, next_cursor = await list_items(
        session, topic_id, cursor=cursor, min_score=min_score, limit=limit
    )
    return FeedPage(
        items=[ItemRead.model_validate(item) for item in rows],
        next_cursor=next_cursor,
    )
