"""管道编排:Retriever → Analyst → Editor → 落库,推进主题调度时间。"""

from datetime import UTC, datetime

import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import TradeWindsError
from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.topic import Topic
from tradewinds.services.item_service import create_pending_items, load_seen_hashes
from tradewinds.services.topic_service import schedule_after
from tradewinds.tools.base import CandidateItem, SourceDegraded

logger = structlog.get_logger(__name__)


class PipelineResult(BaseModel):
    collected: int = 0
    new_items: int = 0
    accepted: int = 0
    rejected: int = 0
    degraded: list[SourceDegraded] = []


class PipelineService:
    def __init__(
        self,
        session: AsyncSession,
        retriever: Retriever,
        analyst: Analyst,
        editor: Editor,
        *,
        score_threshold: float,
    ) -> None:
        self._session = session
        self._retriever = retriever
        self._analyst = analyst
        self._editor = editor
        self._score_threshold = score_threshold

    async def run_topic(self, topic: Topic) -> PipelineResult:
        """手动/定时触发共用入口;重复 run 依赖指纹去重,不产生重复条目。"""
        plan = _plan_of(topic)
        seen_hashes = await load_seen_hashes(self._session, topic.id)
        collected = await self._retriever.collect(plan, topic_id=topic.id, seen_hashes=seen_hashes)
        new_items = await create_pending_items(self._session, topic.id, collected.items)

        accepted = rejected = 0
        if new_items:
            candidates = [_to_candidate(item) for item in new_items]
            scored = await self._analyst.score(candidates, topic)
            items_by_url = {item.url: item for item in new_items}
            for entry in scored:
                db_item = items_by_url.get(entry.item.url)
                if db_item is None:
                    continue
                db_item.score = entry.score
                db_item.cluster_key = entry.cluster_key
                if entry.score >= self._score_threshold:
                    db_item.status = ItemStatus.scored
                    digest = await self._editor.summarize(entry.item, topic)
                    db_item.summary = digest.summary
                    db_item.reason = digest.reason
                    db_item.status = ItemStatus.accepted
                    accepted += 1
                else:
                    db_item.status = ItemStatus.rejected
                    rejected += 1

        now = datetime.now(UTC)
        topic.last_run_at = now
        topic.next_run_at = schedule_after(topic, now=now)
        await self._session.commit()

        if collected.degraded:
            logger.warning(
                "pipeline_degraded_sources", topic_id=topic.id, degraded=collected.degraded
            )
        logger.info(
            "pipeline_run",
            topic_id=topic.id,
            collected=len(collected.items),
            new_items=len(new_items),
            accepted=accepted,
            rejected=rejected,
        )
        return PipelineResult(
            collected=len(collected.items),
            new_items=len(new_items),
            accepted=accepted,
            rejected=rejected,
            degraded=collected.degraded,
        )


def _plan_of(topic: Topic) -> RetrievalPlan:
    try:
        return RetrievalPlan.model_validate(topic.plan or {})
    except ValidationError as exc:
        raise TradeWindsError(
            "检索计划无效,请重新编辑主题", code="plan_invalid", status_code=409
        ) from exc


def _to_candidate(item: Item) -> CandidateItem:
    return CandidateItem(
        source=item.source,
        url=item.url,
        title=item.title,
        raw_content=item.raw_content,
        published_at=item.published_at,
    )
