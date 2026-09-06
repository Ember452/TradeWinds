"""Feed 路由:主题条目的增量 keyset 分页读取。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.api.deps import get_current_user, get_db, get_topic_service
from tradewinds.models.user import User
from tradewinds.services.item_service import list_items
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
