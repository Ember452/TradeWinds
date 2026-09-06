"""主题服务:配额控制、创建时 Planner 编译、归属隔离的增删改查。"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.agents.planner import Planner
from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import NotFoundError, QuotaExceededError
from tradewinds.models.topic import Cadence, Topic, TopicStatus

logger = structlog.get_logger(__name__)

_CADENCE_PERIOD = {Cadence.daily: timedelta(days=1), Cadence.weekly: timedelta(days=7)}


class TopicService:
    def __init__(self, session: AsyncSession, planner: Planner, *, quota_topics_max: int) -> None:
        self._session = session
        self._planner = planner
        self._quota_topics_max = quota_topics_max

    async def create(
        self, user_id: int, *, name: str, description: str, cadence: Cadence
    ) -> tuple[Topic, RetrievalPlan]:
        """创建主题并编译检索计划;超出配额抛 QuotaExceededError。"""
        total = await self._session.scalar(
            select(func.count()).select_from(Topic).where(Topic.user_id == user_id)
        )
        if total is not None and total >= self._quota_topics_max:
            raise QuotaExceededError(f"主题数已达上限({self._quota_topics_max})")

        plan = await self._planner.compile(description, cadence)
        topic = Topic(
            user_id=user_id,
            name=name,
            description=description,
            cadence=cadence,
            plan=plan.model_dump(),
            next_run_at=datetime.now(UTC),
        )
        self._session.add(topic)
        await self._session.commit()
        await self._session.refresh(topic)
        logger.info("topic_created", user_id=user_id, topic_id=topic.id)
        return topic, plan

    async def get(self, user_id: int, topic_id: int) -> Topic:
        """跨用户访问一律 404,不泄露存在性。"""
        topic = await self._session.get(Topic, topic_id)
        if topic is None or topic.user_id != user_id:
            raise NotFoundError("主题不存在")
        return topic

    async def list(self, user_id: int) -> list[Topic]:
        result = await self._session.scalars(
            select(Topic).where(Topic.user_id == user_id).order_by(Topic.created_at.desc())
        )
        return list(result)

    async def update(
        self,
        user_id: int,
        topic_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        cadence: Cadence | None = None,
        status: TopicStatus | None = None,
    ) -> Topic:
        topic = await self.get(user_id, topic_id)
        if name is not None:
            topic.name = name
        if status is not None:
            topic.status = status
        if description is not None:
            topic.description = description
        if cadence is not None:
            topic.cadence = cadence
        # 描述或频率变化 → 重新编译检索计划
        if description is not None or cadence is not None:
            plan = await self._planner.compile(topic.description, topic.cadence)
            topic.plan = plan.model_dump()
        await self._session.commit()
        await self._session.refresh(topic)
        return topic

    async def delete(self, user_id: int, topic_id: int) -> None:
        topic = await self.get(user_id, topic_id)
        await self._session.delete(topic)
        await self._session.commit()


def schedule_after(topic: Topic, *, now: datetime) -> datetime:
    """按频率推进 next_run_at。"""
    return now + _CADENCE_PERIOD[topic.cadence]
