"""push_log:推送审计与内容级去重(同一批条目不重复推送)。"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tradewinds.models.base import Base


class PushStatus(enum.StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class PushType(enum.StrEnum):
    digest = "digest"
    immediate = "immediate"
    report = "report"


class PushLog(Base):
    __tablename__ = "push_log"
    __table_args__ = (
        # 内容级去重:同一主题、同一批条目(URL 集合摘要)只推一次
        UniqueConstraint("topic_id", "digest_key", name="uq_push_log_topic_id_digest_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    digest_key: Mapped[str] = mapped_column(String(64), nullable=False)
    item_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[PushStatus] = mapped_column(
        Enum(PushStatus, native_enum=False, length=16), nullable=False, default=PushStatus.pending
    )
    # digest=周期汇总;immediate=单条高分即时推送;report=周期报告推送
    push_type: Mapped[PushType] = mapped_column(
        Enum(PushType, native_enum=False, length=16),
        nullable=False,
        default=PushType.digest,
        server_default="digest",
    )
    # 即时推送的聚类键:24h 抑制窗口的查询依据(digest 为空)
    cluster_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
