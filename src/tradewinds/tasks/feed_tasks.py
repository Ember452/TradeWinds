"""订阅源健康复检任务:beat 每日执行,更新 feed_sources 状态。"""

import asyncio

import structlog

from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.services.feed_service import FeedService
from tradewinds.tasks.celery_app import RECHECK_FEEDS_TASK, celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name=RECHECK_FEEDS_TASK)
def recheck_feeds_task() -> dict[str, int]:
    return asyncio.run(_recheck_feeds())


async def _recheck_feeds() -> dict[str, int]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        factory = create_session_factory(engine)
        healthy = broken = 0
        async with factory() as session:
            feed_service = FeedService(session)
            for feed in await feed_service.all_feeds():
                result = await feed_service.recheck(feed)
                if result.status.value == "healthy":
                    healthy += 1
                else:
                    broken += 1
        logger.info("feeds_rechecked", healthy=healthy, broken=broken)
        return {"healthy": healthy, "broken": broken}
    finally:
        await engine.dispose()
