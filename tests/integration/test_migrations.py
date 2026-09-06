"""Alembic 迁移集成测试:在真实 PostgreSQL 上 upgrade head / downgrade base。

标记 integration:本地无数据库时默认跳过,CI 起 postgres service 运行。
"""

import asyncio
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


def test_upgrade_creates_tables_and_downgrade_reverts(alembic_config: Config) -> None:
    # 必须是同步测试:alembic env.py 内部 asyncio.run,async 测试的事件循环会与之冲突
    url = os.environ["TRADEWINDS_DATABASE_URL"]

    command.upgrade(alembic_config, "head")
    user_columns = asyncio.run(_table_columns(url, "users"))
    assert {
        "id",
        "email",
        "password_hash",
        "notify_email",
        "quota_topic_max",
        "created_at",
    } <= user_columns
    topic_columns = asyncio.run(_table_columns(url, "topics"))
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
    } <= topic_columns
    item_columns = asyncio.run(_table_columns(url, "items"))
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
    } <= item_columns

    command.downgrade(alembic_config, "base")
    assert not asyncio.run(_table_columns(url, "users"))
    assert not asyncio.run(_table_columns(url, "topics"))
    assert not asyncio.run(_table_columns(url, "items"))
