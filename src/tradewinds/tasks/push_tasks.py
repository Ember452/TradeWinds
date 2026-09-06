"""推送任务:投递 push_log;渠道失败按指数退避重试,重试耗尽保持 failed 可查询。"""

import asyncio
from typing import Any

import structlog

from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.models.push_log import PushStatus
from tradewinds.push.email_channel import EmailChannel, EmailChannelConfig
from tradewinds.services.push_service import PushService
from tradewinds.tasks.celery_app import PUSH_TASK, celery_app

logger = structlog.get_logger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 60


@celery_app.task(name=PUSH_TASK, bind=True, max_retries=_MAX_RETRIES)
def send_push(self: Any, push_log_id: int) -> dict[str, str]:
    try:
        status = asyncio.run(_deliver(push_log_id))
    except Exception as exc:
        logger.error("task_failed", task=PUSH_TASK, push_log_id=push_log_id, error=str(exc))
        raise

    if status == PushStatus.failed and self.request.retries < _MAX_RETRIES:
        # 指数退避:1min、2min、4min;重试耗尽时 push_log 保持 failed 可查询
        raise self.retry(countdown=_RETRY_BASE_SECONDS * (2**self.request.retries))
    return {"status": status.value}


async def _deliver(push_log_id: int) -> PushStatus:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            channel = EmailChannel(
                EmailChannelConfig(
                    host=settings.smtp_host,
                    port=settings.smtp_port,
                    username=settings.smtp_user,
                    password=settings.smtp_password,
                    sender=settings.smtp_from,
                    start_tls=settings.smtp_start_tls,
                )
            )
            push_service = PushService(session, channel, app_base_url=settings.app_base_url)
            return await push_service.deliver(push_log_id)
    finally:
        await engine.dispose()
