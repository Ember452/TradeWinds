"""管道编排:Retriever → Analyst → Editor → 落库,推进主题调度时间。"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.orchestrator.embeddings import Embedder
from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import TradeWindsError
from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.topic import Topic
from tradewinds.services.feed_service import FeedService
from tradewinds.services.item_service import (
    create_pending_items,
    load_seen_hashes,
    recent_accepted_scores,
)
from tradewinds.services.push_service import PushService, effective_immediate_threshold
from tradewinds.services.rag_service import upsert_item_embedding
from tradewinds.services.report_service import ReportService
from tradewinds.services.topic_service import schedule_after
from tradewinds.tools.base import CandidateItem, SourceClient, SourceDegraded

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
        immediate_threshold: float = 8.0,
        suppress_hours: int = 24,
        push_service: PushService | None = None,
        report_service: ReportService | None = None,
        feed_service: FeedService | None = None,
        feed_client_factory: Callable[[Any], SourceClient] | None = None,
        preference_builder: Callable[[int, int], Awaitable[list[str]]] | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._session = session
        self._retriever = retriever
        self._analyst = analyst
        self._editor = editor
        self._score_threshold = score_threshold
        self._immediate_threshold = immediate_threshold
        self._suppress_hours = suppress_hours
        self._push_service = push_service
        self._report_service = report_service
        self._feed_service = feed_service
        self._feed_client_factory = feed_client_factory
        self._embedder = embedder
        self._preference_builder = preference_builder

    async def run_topic(self, topic: Topic) -> PipelineResult:
        """手动/定时触发共用入口;重复 run 依赖指纹去重,不产生重复条目。"""
        plan = _plan_of(topic)
        seen_hashes = await load_seen_hashes(self._session, topic.id)
        # 近期评分历史在新建条目前取,天然排除本次条目
        recent_scores = await recent_accepted_scores(self._session, topic.id)
        extra_clients: list[SourceClient] = []
        if self._feed_service is not None and self._feed_client_factory is not None:
            for feed in await self._feed_service.load_topic_feeds(topic.id):
                extra_clients.append(self._feed_client_factory(feed))
        collected = await self._retriever.collect(
            plan, topic_id=topic.id, seen_hashes=seen_hashes, extra_clients=extra_clients
        )
        new_items = await create_pending_items(self._session, topic.id, collected.items)

        accepted = rejected = 0
        accepted_items: list[Item] = []
        if new_items:
            candidates = [_to_candidate(item) for item in new_items]
            preferences: list[str] = []
            if self._preference_builder is not None:
                preferences = await self._preference_builder(topic.user_id, topic.id)
            scored = await self._analyst.score(candidates, topic, preferences=preferences)
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
                    accepted_items.append(db_item)
                else:
                    db_item.status = ItemStatus.rejected
                    rejected += 1

        now = datetime.now(UTC)
        topic.last_run_at = now
        topic.next_run_at = schedule_after(topic, now=now)
        await self._session.commit()

        if self._embedder is not None:
            for item in accepted_items:
                parts = [item.title, item.summary or "", item.raw_content[:2000]]
                embedding_text = "\n".join(parts)
                await upsert_item_embedding(self._session, item.id, self._embedder, embedding_text)

        if self._push_service is not None and accepted_items:
            await self._push_service.prepare_digest(topic, accepted_items)
            threshold = effective_immediate_threshold(recent_scores, self._immediate_threshold)
            high_score = [item for item in accepted_items if (item.score or 0) >= threshold]
            if high_score:
                await self._push_service.prepare_immediate(
                    topic, high_score, suppress_hours=self._suppress_hours
                )
        if self._report_service is not None:
            report = await self._report_service.upsert_period_report(topic, now=now)
            if self._push_service is not None and report is not None:
                await self._push_service.prepare_report(report)

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
