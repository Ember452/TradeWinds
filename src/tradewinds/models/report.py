"""reports:周期报告(daily/weekly),按主题 x 周期聚合 accepted 条目。

幂等:同一主题同一周期只有一份报告(唯一约束),管道重复 run 只会
重算内容;分享走一次性生成的 share_token(公开访问,不含鉴权)。
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tradewinds.models.base import Base


class ReportPeriodType(enum.StrEnum):
    daily = "daily"
    weekly = "weekly"


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("topic_id", "period_type", "period_start", name="uq_reports_topic_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    period_type: Mapped[ReportPeriodType] = mapped_column(
        Enum(ReportPeriodType, native_enum=False, length=16), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    share_token: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
