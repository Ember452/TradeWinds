"""管道任务:按主题 id 执行一次检索管道;任务内自建事件循环与会话。"""

import asyncio
from typing import Any

import structlog

from tradewinds.agents.runtime import build_pipeline_components
from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.models.topic import Topic
from tradewinds.services.feed_service import FeedService
from tradewinds.services.pipeline_service import PipelineService
from tradewinds.services.preference_service import build_profile
from tradewinds.services.report_service import ReportService
from tradewinds.services.usage_service import SessionUsageRecorder
from tradewinds.tasks.celery_app import PIPELINE_TASK, celery_app
from tradewinds.tools.rss import RssClient

logger = structlog.get_logger(__name__)


@celery_app.task(name=PIPELINE_TASK, bind=True, max_retries=0)
def run_topic_task(self: Any, topic_id: int) -> dict[str, object]:
    """执行一次主题管道。失败不自动重试:下次调度/手动触发即重跑,指纹去重保证幂等。"""
    try:
        return asyncio.run(_run_topic(topic_id))
    except Exception as exc:
        logger.error("task_failed", task=PIPELINE_TASK, topic_id=topic_id, error=str(exc))
        raise


async def _run_topic(topic_id: int) -> dict[str, object]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            topic = await session.get(Topic, topic_id)
            if topic is None:
                logger.warning("topic_not_found", topic_id=topic_id)
                return {"status": "not_found"}

            components = build_pipeline_components(
                settings, usage_recorder=SessionUsageRecorder(factory)
            )
            http_client = components.http_client
            limiter = components.rate_limiter
            try:
                pipeline = PipelineService(
                    session,
                    components.retriever,
                    components.analyst,
                    components.editor,
                    score_threshold=settings.pipeline_score_threshold,
                    immediate_threshold=settings.push_immediate_threshold,
                    suppress_hours=settings.push_cluster_suppress_hours,
                    report_service=ReportService(session),
                    feed_service=FeedService(session, http_client=http_client),
                    feed_client_factory=lambda feed: RssClient(
                        limiter, http_client, feed_id=feed.id, url=feed.url
                    ),
                    preference_builder=lambda user_id, topic_id: build_profile(
                        session, user_id, exclude_topic_id=topic_id
                    ),
                    embedder=components.embedder,
                    push_judge=components.push_judge,
                )
                result = await pipeline.run_topic(topic)
            finally:
                await components.http_client.aclose()

        return {
            "status": "ok",
            "collected": result.collected,
            "new_items": result.new_items,
            "accepted": result.accepted,
            "rejected": result.rejected,
        }
    finally:
        await engine.dispose()
