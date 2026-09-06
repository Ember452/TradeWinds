"""item_clicks:用户点击行为流,跨会话记忆(偏好画像)的行为信号。

用户在 Feed 点开原文 = 对该条目的一次正反馈;偏好画像据此把
对应聚类/关键词加权进后续 Analyst 评分上下文。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from tradewinds.models.base import Base


class ItemClick(Base):
    __tablename__ = "item_clicks"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_item_clicks_user_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
