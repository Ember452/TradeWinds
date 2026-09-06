"""add topics and items tables

Revision ID: 0002_topics_items
Revises: 0001_users
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002_topics_items"
down_revision: str | None = "0001_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_topics_users_user_id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("plan", JSONB(), nullable=True),
        sa.Column(
            "cadence",
            sa.Enum("daily", "weekly", name="cadence", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "muted", name="topicstatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_topics_user_id", "topics", ["user_id"])

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("topics.id", ondelete="CASCADE", name="fk_items_topics_topic_id"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("cluster_key", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "scored",
                "accepted",
                "rejected",
                name="itemstatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("topic_id", "url_hash", name="uq_items_topic_id_url_hash"),
    )
    op.create_index("ix_items_topic_id", "items", ["topic_id"])
    op.create_index("ix_items_status", "items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_items_status", table_name="items")
    op.drop_index("ix_items_topic_id", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_topics_user_id", table_name="topics")
    op.drop_table("topics")
