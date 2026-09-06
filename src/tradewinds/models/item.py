"""items 表:检索管道产出的信息条目,状态流转 pending → scored → accepted|rejected。"""

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from tradewinds.models.base import Base


class ItemStatus(enum.StrEnum):
    pending = "pending"
    scored = "scored"
    accepted = "accepted"
    rejected = "rejected"


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        # url_hash = sha256(规范化 url),主题内去重
        UniqueConstraint("topic_id", "url_hash", name="uq_items_topic_id_url_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, native_enum=False, length=16),
        nullable=False,
        default=ItemStatus.pending,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
