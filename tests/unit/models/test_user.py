"""User 模型结构测试(不依赖真实数据库)。"""

from sqlalchemy import UniqueConstraint

from tradewinds.models.user import User


def test_table_name_is_plural() -> None:
    assert User.__tablename__ == "users"


def test_contract_columns_exist() -> None:
    columns = set(User.__table__.columns.keys())

    assert {
        "id",
        "email",
        "password_hash",
        "notify_email",
        "quota_topic_max",
        "created_at",
    } <= columns


def test_email_is_unique() -> None:
    unique_constraints = {
        tuple(col.name for col in constraint.columns)
        for constraint in User.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {
        tuple(col.name for col in idx.columns) for idx in User.__table__.indexes if idx.unique
    }

    assert ("email",) in unique_constraints | indexes
