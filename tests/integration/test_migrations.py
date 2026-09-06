"""Alembic 迁移集成测试:在真实 PostgreSQL 上 upgrade head / downgrade base。

标记 integration:本地无数据库时默认跳过,CI 起 postgres service 运行。
迁移验证在一次性独立数据库上进行——downgrade 会清库,绝不能指向
共享的测试数据库,否则排在后面的测试全部失去表结构。
"""

import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

_MIGRATION_DB = "tradewinds_migration_test"


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


async def _recreate_database(admin_url: str, name: str) -> None:
    """DROP IF EXISTS + CREATE,必须在 AUTOCOMMIT 连接上执行(CREATE DATABASE 不允许在事务内)。"""
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()


async def _drop_database(admin_url: str, name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()


def test_upgrade_creates_tables_and_downgrade_reverts(
    alembic_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 必须是同步测试:alembic env.py 内部 asyncio.run,async 测试的事件循环会与之冲突
    admin_url = os.environ["TRADEWINDS_DATABASE_URL"]
    test_db_url = f"{admin_url.rsplit('/', 1)[0]}/{_MIGRATION_DB}"
    asyncio.run(_recreate_database(admin_url, _MIGRATION_DB))
    # env.py 每次命令加载时直读该环境变量,指向一次性库
    monkeypatch.setenv("TRADEWINDS_DATABASE_URL", test_db_url)
    try:
        command.upgrade(alembic_config, "head")
        user_columns = asyncio.run(_table_columns(test_db_url, "users"))
        assert {
            "id",
            "email",
            "password_hash",
            "notify_email",
            "quota_topic_max",
            "created_at",
        } <= user_columns
        topic_columns = asyncio.run(_table_columns(test_db_url, "topics"))
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
        item_columns = asyncio.run(_table_columns(test_db_url, "items"))
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
        assert not asyncio.run(_table_columns(test_db_url, "users"))
        assert not asyncio.run(_table_columns(test_db_url, "topics"))
        assert not asyncio.run(_table_columns(test_db_url, "items"))
    finally:
        asyncio.run(_drop_database(admin_url, _MIGRATION_DB))
