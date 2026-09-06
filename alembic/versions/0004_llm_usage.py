"""llm usage records 迁移。

Revision ID: 0004_llm_usage
Revises: 0003_push_log
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_llm_usage"
down_revision: str | None = "0003_push_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name="fk_llm_usage_records_users_user_id"
            ),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=8), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_llm_usage_records_user_id_created_at", "llm_usage_records", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_records_user_id_created_at", table_name="llm_usage_records")
    op.drop_table("llm_usage_records")
