"""reports 迁移。

Revision ID: 0006_reports
Revises: 0005_conversations
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006_reports"
down_revision: str | None = "0005_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("topics.id", ondelete="CASCADE", name="fk_reports_topics_topic_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_reports_users_user_id"),
            nullable=False,
        ),
        sa.Column(
            "period_type",
            sa.Enum("daily", "weekly", name="reportperiodtype", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_ids", JSONB(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("share_token", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "topic_id", "period_type", "period_start", name="uq_reports_topic_period"
        ),
    )
    op.create_index("ix_reports_topic_id", "reports", ["topic_id"])
    op.create_index("ix_reports_share_token", "reports", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_reports_share_token", table_name="reports")
    op.drop_index("ix_reports_topic_id", table_name="reports")
    op.drop_table("reports")
