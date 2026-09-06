"""feed_sources 迁移。

Revision ID: 0008_feed_sources
Revises: 0007_push_type
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_feed_sources"
down_revision: str | None = "0007_push_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feed_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_feed_sources_users_user_id"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("topics.id", ondelete="CASCADE", name="fk_feed_sources_topics_topic_id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "status",
            sa.Enum("healthy", "broken", name="feedstatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("topic_id", "url", name="uq_feed_sources_topic_id_url"),
    )
    op.create_index("ix_feed_sources_topic_id", "feed_sources", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_feed_sources_topic_id", table_name="feed_sources")
    op.drop_table("feed_sources")
