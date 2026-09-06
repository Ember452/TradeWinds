"""Alembic 迁移集成测试:在真实 PostgreSQL 上 upgrade head / downgrade base。

标记 integration:本地无数据库时默认跳过,CI 起 postgres service 运行。
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


@pytest.fixture
def alembic_config() -> Config:
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    return Config("alembic.ini")


async def _table_columns(database_url: str, table: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :table AND table_schema = 'public'"
                ),
                {"table": table},
            )
            return {row[0] for row in rows}
    finally:
        await engine.dispose()


async def test_upgrade_creates_users_and_downgrade_reverts(alembic_config: Config) -> None:
    url = os.environ["TRADEWINDS_DATABASE_URL"]

    command.upgrade(alembic_config, "head")
    columns = await _table_columns(url, "users")
    assert {
        "id",
        "email",
        "password_hash",
        "notify_email",
        "quota_topic_max",
        "created_at",
    } <= columns

    command.downgrade(alembic_config, "base")
    assert not await _table_columns(url, "users")
