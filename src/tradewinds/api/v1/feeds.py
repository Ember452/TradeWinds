"""自定义订阅源路由:提交(创建即健康校验)、列表、删除。"""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from tradewinds.api.deps import get_current_user, get_feed_service
from tradewinds.models.feed_source import FeedStatus
from tradewinds.models.user import User
from tradewinds.services.feed_service import FeedService

router = APIRouter(tags=["feeds"])


class FeedCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    title: str | None = Field(default=None, max_length=200)


class FeedRead(BaseModel):
    id: int
    topic_id: int
    title: str
    url: str
    status: FeedStatus
    last_checked_at: datetime | None
    last_ok_at: datetime | None

    model_config = {"from_attributes": True}


@router.post(
    "/topics/{topic_id}/feeds", response_model=FeedRead, status_code=status.HTTP_201_CREATED
)
async def add_feed(
    topic_id: int,
    payload: FeedCreate,
    current_user: User = Depends(get_current_user),
    feed_service: FeedService = Depends(get_feed_service),
) -> FeedRead:
    """提交自定义源;创建前做健康校验(不可解析 → 422 invalid_feed)。"""
    feed = await feed_service.add(current_user.id, topic_id, url=payload.url, title=payload.title)
    return FeedRead.model_validate(feed)


@router.get("/topics/{topic_id}/feeds", response_model=list[FeedRead])
async def list_feeds(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    feed_service: FeedService = Depends(get_feed_service),
) -> list[FeedRead]:
    return [
        FeedRead.model_validate(feed)
        for feed in await feed_service.list_for_topic(current_user.id, topic_id)
    ]


@router.delete("/topics/{topic_id}/feeds/{feed_id}")
async def delete_feed(
    topic_id: int,
    feed_id: int,
    current_user: User = Depends(get_current_user),
    feed_service: FeedService = Depends(get_feed_service),
) -> dict[str, str]:
    await feed_service.delete(current_user.id, feed_id)
    return {"message": "已删除"}
