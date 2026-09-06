"""管道任务:按主题 id 执行一次检索管道;任务内自建事件循环与会话。"""

import asyncio
from typing import Any

import structlog

from tradewinds.agents.runtime import build_pipeline_components
from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.models.topic import Topic
from tradewinds.services.pipeline_service import PipelineService
from tradewinds.tasks.celery_app import PIPELINE_TASK, celery_app

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

            components = build_pipeline_components(settings)
            try:
                pipeline = PipelineService(
                    session,
                    components.retriever,
                    components.analyst,
                    components.editor,
                    score_threshold=settings.pipeline_score_threshold,
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
