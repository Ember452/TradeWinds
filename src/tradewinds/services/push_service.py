"""推送服务:内容级去重、push_log 审计、投递;入队分发由组合方注入。"""

import hashlib
import statistics
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.models.item import Item
from tradewinds.models.push_log import PushLog, PushStatus, PushType
from tradewinds.models.topic import Topic
from tradewinds.models.user import User
from tradewinds.push.base import PushChannel
from tradewinds.push.templates import render_digest_email, render_item_alert_email

logger = structlog.get_logger(__name__)


def digest_key_of(urls: list[str]) -> str:
    """内容指纹:URL 排序后哈希,与条目顺序无关。"""
    return hashlib.sha256("|".join(sorted(urls)).encode()).hexdigest()


def effective_immediate_threshold(
    recent_scores: Sequence[float],
    global_threshold: float,
    *,
    min_history: int = 10,
    adjust: float = 1.0,
) -> float:
    """按主题近期表现自适应即时推送阈值(扩展计划 §3 阈值动态化)。

    冷启动(历史不足 min_history)用全局值;否则以近期评分中位数在
    [global-adjust, global+adjust] 内浮动:高分主题抬高门槛避免刷屏,
    低分主题轻微下调浮出精华。
    """
    if len(recent_scores) < min_history:
        return global_threshold
    median = statistics.median(recent_scores)
    return min(global_threshold + adjust, max(global_threshold - adjust, median))


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

    async def prepare_immediate(
        self, topic: Topic, items: list[Item], *, suppress_hours: int, now: datetime | None = None
    ) -> list[PushLog]:
        """即时推送:逐条建 PushLog 并入队;同聚类 24h 内已推送则抑制,单条重复也不重推。"""
        now = now or datetime.now(UTC)
        user = await self._session.get(User, topic.user_id)
        if user is None:
            return []

        created: list[PushLog] = []
        for item in items:
            if item.cluster_key is not None and await self._cluster_suppressed(
                topic.id, item.cluster_key, suppress_hours=suppress_hours, now=now
            ):
                continue
            digest_key = f"item:{item.id}"
            existing = await self._session.scalar(
                select(PushLog).where(
                    PushLog.topic_id == topic.id, PushLog.digest_key == digest_key
                )
            )
            if existing is not None:
                continue

            log = PushLog(
                topic_id=topic.id,
                user_id=topic.user_id,
                channel=self._channel.name,
                digest_key=digest_key,
                item_ids=[item.id],
                recipient=user.email,
                status=PushStatus.pending,
                push_type=PushType.immediate,
                cluster_key=item.cluster_key,
            )
            self._session.add(log)
            await self._session.commit()
            await self._session.refresh(log)
            if self._dispatch is not None:
                self._dispatch(log.id)
            created.append(log)
            logger.info(
                "immediate_push_prepared", push_log_id=log.id, topic_id=topic.id, item_id=item.id
            )
        return created

    async def _cluster_suppressed(
        self, topic_id: int, cluster_key: str, *, suppress_hours: int, now: datetime
    ) -> bool:
        """同聚类在抑制窗口内已有待发/已发的即时推送 → 抑制。"""
        window_start = now - timedelta(hours=suppress_hours)
        recent = await self._session.scalar(
            select(PushLog.id)
            .where(PushLog.topic_id == topic_id)
            .where(PushLog.push_type == PushType.immediate)
            .where(PushLog.cluster_key == cluster_key)
            .where(PushLog.status.in_([PushStatus.pending, PushStatus.sent]))
            .where(PushLog.created_at >= window_start)
        )
        return recent is not None

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

        if log.push_type is PushType.immediate and len(items) == 1:
            payload = render_item_alert_email(
                topic=topic, item=items[0], to=log.recipient, app_base_url=self._app_base_url
            )
        else:
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
