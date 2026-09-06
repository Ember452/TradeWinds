"""到期主题扫描与管道任务集成测试:真实 PostgreSQL;任务以 eager 方式本地执行。

标记 integration:CI 起 PostgreSQL/Redis service 运行。
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tradewinds.api.app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        yield test_client


async def _create_topic_raw(topic_id_expect: bool, *, next_run_at: datetime, status: str) -> int:
    """直接落一条 topic(绕过 API,聚焦调度查询语义)。"""
    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            user_row = await conn.execute(
                text("INSERT INTO users (email, password_hash) VALUES (:email, 'x') RETURNING id"),
                {"email": f"sched-{uuid.uuid4().hex[:10]}@example.com"},
            )
            user_id = user_row.scalar_one()
            row = await conn.execute(
                text(
                    "INSERT INTO topics (user_id, name, description, cadence, status, next_run_at) "
                    "VALUES (:uid, 't', 'd', 'weekly', :status, :next_run_at) RETURNING id"
                ),
                {"uid": user_id, "status": status, "next_run_at": next_run_at},
            )
            return int(row.scalar_one())
    finally:
        await engine.dispose()


def test_find_due_topic_ids_filters_by_status_and_time(client: TestClient) -> None:
    import asyncio

    from tradewinds.core.config import get_settings
    from tradewinds.core.database import create_engine, create_session_factory
    from tradewinds.services.topic_service import find_due_topic_ids

    now = datetime.now(UTC)
    due_id = asyncio.run(
        _create_topic_raw(True, next_run_at=now - timedelta(minutes=1), status="active")
    )
    future_id = asyncio.run(
        _create_topic_raw(True, next_run_at=now + timedelta(days=1), status="active")
    )
    muted_id = asyncio.run(
        _create_topic_raw(True, next_run_at=now - timedelta(minutes=1), status="muted")
    )

    async def _scan() -> list[int]:
        settings = get_settings()
        engine = create_engine(settings.database_url)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                return await find_due_topic_ids(session, now=now)
        finally:
            await engine.dispose()

    due = asyncio.run(_scan())

    assert due_id in due
    assert future_id not in due
    assert muted_id not in due
