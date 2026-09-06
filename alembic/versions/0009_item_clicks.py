"""item_clicks 迁移。

Revision ID: 0009_item_clicks
Revises: 0008_feed_sources
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_item_clicks"
down_revision: str | None = "0008_feed_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_clicks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_item_clicks_users_user_id"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="CASCADE", name="fk_item_clicks_items_item_id"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "item_id", name="uq_item_clicks_user_item"),
    )
    op.create_index("ix_item_clicks_user_id", "item_clicks", ["user_id"])
    op.create_index("ix_item_clicks_item_id", "item_clicks", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_item_clicks_item_id", table_name="item_clicks")
    op.drop_index("ix_item_clicks_user_id", table_name="item_clicks")
    op.drop_table("item_clicks")
