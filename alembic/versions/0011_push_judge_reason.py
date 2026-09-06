"""push_log 增 judge_reason:即时推送 LLM Judge 的判定依据(审计留痕)。

Revision ID: 0011_push_judge_reason
Revises: 0010_item_embeddings
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_push_judge_reason"
down_revision: str | None = "0010_item_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("push_log", sa.Column("judge_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("push_log", "judge_reason")
