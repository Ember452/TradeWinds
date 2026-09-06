"""Topic 模型结构测试(不依赖真实数据库)。"""

from tradewinds.models.topic import Cadence, Topic, TopicStatus


def test_table_name_is_plural() -> None:
    assert Topic.__tablename__ == "topics"


def test_contract_columns_exist() -> None:
    columns = set(Topic.__table__.columns.keys())

    assert {
        "id",
        "user_id",
        "name",
        "description",
        "plan",
        "cadence",
        "status",
        "last_run_at",
        "next_run_at",
        "created_at",
    } <= columns


def test_user_foreign_key() -> None:
    foreign_keys = list(Topic.__table__.columns["user_id"].foreign_keys)

    assert any(fk.column.table.name == "users" for fk in foreign_keys)


def test_cadence_and_status_enums() -> None:
    assert {c.value for c in Cadence} == {"daily", "weekly"}
    assert {c.value for c in TopicStatus} == {"active", "muted"}
