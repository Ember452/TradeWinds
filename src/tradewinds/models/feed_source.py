"""feed_sources:用户为主题提交的自定义 RSS/Atom 订阅源。

创建时做一次健康校验(必须可解析);beat 每日复检更新状态。
管道检索时该主题的全部自定义源(含 broken,标注降级)都会被抓取。
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from tradewinds.models.base import Base


class FeedStatus(enum.StrEnum):
    healthy = "healthy"
    broken = "broken"


class FeedSource(Base):
    __tablename__ = "feed_sources"
    __table_args__ = (
        # 同一主题不重复提交同一 URL(URL 规范化后仍以原文存储)
        UniqueConstraint("topic_id", "url", name="uq_feed_sources_topic_id_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[FeedStatus] = mapped_column(
        Enum(FeedStatus, native_enum=False, length=16),
        nullable=False,
        default=FeedStatus.healthy,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
