"""主题路由:创建(返回 Planner 计划预览)、增删改查、手动执行。"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from tradewinds.api.deps import get_current_user, get_pipeline_service, get_topic_service
from tradewinds.models.topic import Cadence, Topic, TopicStatus
from tradewinds.models.user import User
from tradewinds.services.pipeline_service import PipelineService
from tradewinds.services.topic_service import TopicService

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    cadence: Cadence


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    cadence: Cadence | None = None
    status: TopicStatus | None = None


class TopicRead(BaseModel):
    id: int
    name: str
    description: str
    cadence: Cadence
    status: TopicStatus
    plan: dict[str, Any] | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TopicCreatedResponse(BaseModel):
    topic: TopicRead
    plan: dict[str, Any]


class PipelineRunRead(BaseModel):
    collected: int
    new_items: int
    accepted: int
    rejected: int
    degraded: list[dict[str, str]]


class MessageResponse(BaseModel):
    message: str


def _to_read(topic: Topic) -> TopicRead:
    return TopicRead.model_validate(topic)


@router.post("", response_model=TopicCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicCreate,
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
) -> TopicCreatedResponse:
    topic, plan = await topic_service.create(
        current_user.id, name=payload.name, description=payload.description, cadence=payload.cadence
    )
    return TopicCreatedResponse(topic=_to_read(topic), plan=plan.model_dump())


@router.get("", response_model=list[TopicRead])
async def list_topics(
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
) -> list[TopicRead]:
    return [_to_read(topic) for topic in await topic_service.list(current_user.id)]


@router.get("/{topic_id}", response_model=TopicRead)
async def get_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
) -> TopicRead:
    return _to_read(await topic_service.get(current_user.id, topic_id))


@router.patch("/{topic_id}", response_model=TopicRead)
async def update_topic(
    topic_id: int,
    payload: TopicUpdate,
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
) -> TopicRead:
    topic = await topic_service.update(
        current_user.id,
        topic_id,
        name=payload.name,
        description=payload.description,
        cadence=payload.cadence,
        status=payload.status,
    )
    return _to_read(topic)


@router.delete("/{topic_id}", response_model=MessageResponse)
async def delete_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
) -> MessageResponse:
    await topic_service.delete(current_user.id, topic_id)
    return MessageResponse(message="已删除")


@router.post("/{topic_id}/mute", response_model=TopicRead)
async def mute_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
) -> TopicRead:
    """退订:暂停该主题的定时执行与推送(Feed 保留)。"""
    topic = await topic_service.update(current_user.id, topic_id, status=TopicStatus.muted)
    return _to_read(topic)


@router.post("/{topic_id}/run", response_model=PipelineRunRead)
async def run_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    topic_service: TopicService = Depends(get_topic_service),
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> PipelineRunRead:
    """手动触发一次管道执行(Phase 3 起 Celery worker 异步执行)。"""
    topic = await topic_service.get(current_user.id, topic_id)
    result = await pipeline.run_topic(topic)
    return PipelineRunRead(
        collected=result.collected,
        new_items=result.new_items,
        accepted=result.accepted,
        rejected=result.rejected,
        degraded=[{"source": d.source, "reason": d.reason} for d in result.degraded],
    )
