"""演示数据 seed 集成测试:重复执行幂等,不产生重复数据。

标记 integration:本地无数据库时默认跳过,CI 起 postgres service 运行。
"""

import os
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tradewinds.core.database import create_session_factory
from tradewinds.demo_seed import DEMO_EMAIL, seed_demo

pytestmark = pytest.mark.integration


@pytest.fixture
async def session_factory():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def _counts(database_url: str) -> dict[str, int]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM topics t JOIN users u ON u.id = t.user_id "
                    " WHERE u.email = :email) AS topics, "
                    "(SELECT COUNT(*) FROM items i JOIN topics t ON t.id = i.topic_id "
                    "  JOIN users u ON u.id = t.user_id WHERE u.email = :email) AS items, "
                    "(SELECT COUNT(*) FROM push_log p JOIN users u ON u.id = p.user_id "
                    " WHERE u.email = :email) AS pushes, "
                    "(SELECT COUNT(*) FROM reports r JOIN users u ON u.id = r.user_id "
                    " WHERE u.email = :email) AS reports"
                ),
                {"email": DEMO_EMAIL},
            )
            row: dict[str, Any] = dict(rows.mappings().one())
            return {k: int(v) for k, v in row.items()}
    finally:
        await engine.dispose()


async def test_seed_is_idempotent(session_factory) -> None:
    # 首次执行写入(或此库此前已 seed 过);第二次必须跳过且数据不变
    async with session_factory() as session:
        await seed_demo(session)
    before = await _counts(os.environ["TRADEWINDS_DATABASE_URL"])

    async with session_factory() as session:
        assert await seed_demo(session) is False
    after = await _counts(os.environ["TRADEWINDS_DATABASE_URL"])

    assert before == after
    assert after["topics"] >= 2
    assert after["items"] >= 10
    assert after["reports"] >= 1
    assert after["pushes"] >= 2
