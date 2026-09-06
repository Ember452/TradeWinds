"""调度任务:beat 每分钟扫描到期主题并入队;Redis 分布式锁防多实例重复扫描。"""

import asyncio
from datetime import UTC, datetime

import structlog

from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.core.redis_client import create_redis_client
from tradewinds.services.topic_service import find_due_topic_ids
from tradewinds.tasks.celery_app import SCAN_TASK, celery_app
from tradewinds.tasks.pipeline_tasks import run_topic_task

logger = structlog.get_logger(__name__)

_LOCK_KEY = "tradewinds:scan_due_topics:lock"
_LOCK_TTL_SECONDS = 55


@celery_app.task(name=SCAN_TASK)
def scan_due_topics_task() -> dict[str, object]:
    return asyncio.run(_scan_due_topics())


async def _scan_due_topics() -> dict[str, object]:
    settings = get_settings()
    redis = create_redis_client(settings.redis_url)
    try:
        # beat 可能多实例部署:锁内扫描入队,未被锁者本分钟直接让过
        lock = redis.lock(_LOCK_KEY, timeout=_LOCK_TTL_SECONDS, blocking=False)
        if not await lock.acquire():
            return {"enqueued": 0, "locked_out": True}

        try:
            topic_ids = await _collect_due_topic_ids()
            for topic_id in topic_ids:
                run_topic_task.apply_async(args=[topic_id], queue="pipeline")
            if topic_ids:
                logger.info("due_topics_enqueued", count=len(topic_ids), topic_ids=topic_ids)
            return {"enqueued": len(topic_ids)}
        finally:
            await lock.release()
    finally:
        await redis.aclose()


async def _collect_due_topic_ids() -> list[int]:
    engine = create_engine(get_settings().database_url)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            return await find_due_topic_ids(session, now=datetime.now(UTC))
    finally:
        await engine.dispose()
