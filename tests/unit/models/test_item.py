"""Item 模型结构测试(不依赖真实数据库)。"""

from sqlalchemy import UniqueConstraint

from tradewinds.models.item import Item, ItemStatus


def test_table_name_is_plural() -> None:
    assert Item.__tablename__ == "items"


def test_contract_columns_exist() -> None:
    columns = set(Item.__table__.columns.keys())

    assert {
        "id",
        "topic_id",
        "source",
        "url",
        "url_hash",
        "title",
        "raw_content",
        "published_at",
        "score",
        "cluster_key",
        "summary",
        "reason",
        "status",
        "created_at",
    } <= columns


def test_url_hash_unique_within_topic() -> None:
    multi_column_uniques = [
        tuple(col.name for col in constraint.columns)
        for constraint in Item.__table__.constraints
        if isinstance(constraint, UniqueConstraint) and len(constraint.columns) > 1
    ]

    assert ("topic_id", "url_hash") in multi_column_uniques


def test_status_lifecycle_enum() -> None:
    assert {c.value for c in ItemStatus} == {"pending", "scored", "accepted", "rejected"}
