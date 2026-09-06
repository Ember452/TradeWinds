"""推送服务:内容级去重、push_log 审计、投递;入队分发由组合方注入。"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.models.item import Item
from tradewinds.models.push_log import PushLog, PushStatus
from tradewinds.models.topic import Topic
from tradewinds.models.user import User
from tradewinds.push.base import PushChannel
from tradewinds.push.templates import render_digest_email

logger = structlog.get_logger(__name__)


def digest_key_of(urls: list[str]) -> str:
    """内容指纹:URL 排序后哈希,与条目顺序无关。"""
    return hashlib.sha256("|".join(sorted(urls)).encode()).hexdigest()


class PushService:
    def __init__(
        self,
        session: AsyncSession,
        channel: PushChannel,
        *,
        app_base_url: str,
        dispatch: Callable[[int], object] | None = None,
    ) -> None:
        self._session = session
        self._channel = channel
        self._app_base_url = app_base_url
        # 入队回调由组合方注入(tasks 层),服务层不反向依赖任务模块
        self._dispatch = dispatch

    async def prepare_digest(self, topic: Topic, items: list[Item]) -> PushLog | None:
        """为一批 accepted 条目建推送记录并入队;同批内容此前已推过则跳过。"""
        if not items:
            return None

        key = digest_key_of([item.url for item in items])
        existing = await self._session.scalar(
            select(PushLog).where(PushLog.topic_id == topic.id, PushLog.digest_key == key)
        )
        if existing is not None:
            return None

        user = await self._session.get(User, topic.user_id)
        if user is None:
            logger.warning("push_user_not_found", topic_id=topic.id)
            return None

        log = PushLog(
            topic_id=topic.id,
            user_id=topic.user_id,
            channel=self._channel.name,
            digest_key=key,
            item_ids=[item.id for item in items],
            recipient=user.email,
            status=PushStatus.pending,
        )
        self._session.add(log)
        await self._session.commit()
        await self._session.refresh(log)

        if self._dispatch is not None:
            self._dispatch(log.id)
        logger.info("push_prepared", push_log_id=log.id, topic_id=topic.id, items=len(items))
        return log

    async def deliver(self, push_log_id: int) -> PushStatus:
        """投递单条推送并回写状态;渠道失败不抛异常,记入 push_log 可查询。"""
        log = await self._session.get(PushLog, push_log_id)
        if log is None:
            logger.warning("push_log_not_found", push_log_id=push_log_id)
            return PushStatus.failed

        items = list(
            (await self._session.scalars(select(Item).where(Item.id.in_(log.item_ids)))).all()
        )
        topic = await self._session.get(Topic, log.topic_id)
        user = await self._session.get(User, log.user_id)
        if topic is None or user is None or not items:
            log.status = PushStatus.failed
            log.error = "推送内容已不存在"
            await self._session.commit()
            return PushStatus.failed

        payload = render_digest_email(
            topic=topic, items=items, to=log.recipient, app_base_url=self._app_base_url
        )
        receipt = await self._channel.send(payload)

        if receipt.ok:
            log.status = PushStatus.sent
            log.sent_at = datetime.now(UTC)
        elif receipt.error == "email_disabled":
            log.status = PushStatus.skipped
            log.error = receipt.error
        else:
            log.status = PushStatus.failed
            log.error = receipt.error

        await self._session.commit()
        logger.info("push_delivered", push_log_id=log.id, status=log.status.value, error=log.error)
        return log.status
