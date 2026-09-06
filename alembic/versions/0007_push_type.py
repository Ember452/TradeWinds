"""push_log 增加推送类型与聚类键(即时推送 + 聚类抑制)。

Revision ID: 0007_push_type
Revises: 0006_reports
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_push_type"
down_revision: str | None = "0006_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "push_log",
        sa.Column(
            "push_type",
            sa.Enum("digest", "immediate", name="pushtype", native_enum=False, length=16),
            nullable=False,
            server_default="digest",
        ),
    )
    op.add_column("push_log", sa.Column("cluster_key", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_push_log_topic_cluster_time",
        "push_log",
        ["topic_id", "cluster_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_log_topic_cluster_time", table_name="push_log")
    op.drop_column("push_log", "cluster_key")
    op.drop_column("push_log", "push_type")
