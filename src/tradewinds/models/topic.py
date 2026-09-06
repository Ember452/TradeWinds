"""topics 表:用户的订阅主题。plan 字段存放 Planner 编译出的检索计划(JSON)。"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tradewinds.models.base import Base


class Cadence(enum.StrEnum):
    daily = "daily"
    weekly = "weekly"


class TopicStatus(enum.StrEnum):
    active = "active"
    muted = "muted"


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Planner 编译产物:keywords/sources/window_days/relevance_criteria 等
    plan: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    cadence: Mapped[Cadence] = mapped_column(
        Enum(Cadence, native_enum=False, length=16), nullable=False
    )
    status: Mapped[TopicStatus] = mapped_column(
        Enum(TopicStatus, native_enum=False, length=16),
        nullable=False,
        default=TopicStatus.active,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
