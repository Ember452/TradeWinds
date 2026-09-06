"""自定义订阅源服务:创建时健康校验、归属隔离 CRUD、每日复检。"""

from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.exceptions import NotFoundError, TradeWindsError
from tradewinds.models.feed_source import FeedSource, FeedStatus
from tradewinds.models.topic import Topic
from tradewinds.tools.base import PassthroughLimiter
from tradewinds.tools.http import fetch_text
from tradewinds.tools.rss import parse_feed

logger = structlog.get_logger(__name__)

_PROBE_MAX_CHARS = 100_000


class FeedService:
    def __init__(
        self, session: AsyncSession, *, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self._session = session
        self._http_client = http_client or httpx.AsyncClient(timeout=30, follow_redirects=True)

    async def add(self, user_id: int, topic_id: int, *, url: str, title: str | None) -> FeedSource:
        """提交自定义源:创建前先抓取并解析一次,失败抛 invalid_feed(422)。"""
        topic = await self._session.get(Topic, topic_id)
        if topic is None or topic.user_id != user_id:
            raise NotFoundError("主题不存在")

        normalized = url.strip()
        if not normalized.startswith(("http://", "https://")):
            raise TradeWindsError("订阅源必须是 http(s) URL", code="invalid_feed", status_code=422)

        await self._probe(normalized)  # 健康校验失败直接 422

        duplicate = await self._session.scalar(
            select(FeedSource).where(FeedSource.topic_id == topic_id, FeedSource.url == normalized)
        )
        if duplicate is not None:
            raise TradeWindsError("该订阅源已存在", code="duplicate_feed", status_code=409)

        feed = FeedSource(
            user_id=user_id,
            topic_id=topic_id,
            title=(title or normalized)[:200],
            url=normalized,
            status=FeedStatus.healthy,
            last_checked_at=datetime.now(UTC),
            last_ok_at=datetime.now(UTC),
        )
        self._session.add(feed)
        await self._session.commit()
        await self._session.refresh(feed)
        logger.info("feed_added", feed_id=feed.id, topic_id=topic_id)
        return feed

    async def list_for_topic(self, user_id: int, topic_id: int) -> list[FeedSource]:
        topic = await self._session.get(Topic, topic_id)
        if topic is None or topic.user_id != user_id:
            raise NotFoundError("主题不存在")
        result = await self._session.scalars(
            select(FeedSource)
            .where(FeedSource.topic_id == topic_id)
            .order_by(FeedSource.created_at.desc())
        )
        return list(result)

    async def delete(self, user_id: int, feed_id: int) -> None:
        feed = await self._session.get(FeedSource, feed_id)
        if feed is None or feed.user_id != user_id:
            raise NotFoundError("订阅源不存在")
        await self._session.delete(feed)
        await self._session.commit()

    async def load_topic_feeds(self, topic_id: int) -> list[FeedSource]:
        """管道检索用:该主题全部自定义源(broken 也抓取,降级标注可见)。"""
        result = await self._session.scalars(
            select(FeedSource).where(FeedSource.topic_id == topic_id)
        )
        return list(result)

    async def all_feeds(self) -> list[FeedSource]:
        result = await self._session.scalars(select(FeedSource).order_by(FeedSource.id))
        return list(result)

    async def recheck(self, feed: FeedSource) -> FeedSource:
        """复检单个源:可解析 → healthy,否则 broken;不抛异常。"""
        now = datetime.now(UTC)
        try:
            await self._probe(feed.url)
            feed.status = FeedStatus.healthy
            feed.last_ok_at = now
        except TradeWindsError:
            feed.status = FeedStatus.broken
        feed.last_checked_at = now
        await self._session.commit()
        logger.info("feed_rechecked", feed_id=feed.id, status=feed.status.value)
        return feed

    async def _probe(self, url: str) -> None:
        """健康校验:HTTP 可达 + 正文可解析为 RSS/Atom。"""
        try:
            body = await fetch_text(PassthroughLimiter(), self._http_client, url)
            parse_feed(body)
        except TradeWindsError as exc:
            raise TradeWindsError(
                "订阅源无法访问或不是有效的 RSS/Atom", code="invalid_feed", status_code=422
            ) from exc
