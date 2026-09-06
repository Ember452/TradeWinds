"""启用 pgvector 扩展并创建 item_embeddings 表。

向量列不锁定维度(untyped vector):MVP 用精确余弦检索、无需 ivfflat 索引,
且更换嵌入模型(维度变化)时无需改表;数据量到达需要 ANN 索引的规模时,
先固定维度再建索引(升级路径见 docs/study/15)。

Revision ID: 0010_item_embeddings
Revises: 0009_item_clicks
Create Date: 2026-09-06

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_item_embeddings"
down_revision: str | None = "0009_item_clicks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE item_embeddings (
            item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
            embedding vector NOT NULL,
            model VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.drop_table("item_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
