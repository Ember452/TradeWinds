"""Feed keyset 分页集成测试:分页正确性、索引使用、跨用户 404。

标记 integration:CI 起 PostgreSQL/Redis service 运行。
"""

import os
import uuid

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


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    email = f"feed-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_topic_with_items(client: TestClient, headers: dict[str, str], item_count: int) -> int:
    resp = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "Feed 主题", "description": "feed test", "cadence": "weekly"},
    )
    assert resp.status_code == 201, resp.text
    topic_id = resp.json()["topic"]["id"]

    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        import asyncio

        async def _insert() -> None:
            async with engine.begin() as conn:
                insert_sql = (
                    "INSERT INTO items (topic_id, source, url, url_hash, title,"
                    " raw_content, score, cluster_key, summary, reason, status)"
                    " VALUES (:t, 'arxiv', :url, :hash, :title, 'c', :score,"
                    " 'k', 's', 'r', :status)"
                )
                for i in range(item_count):
                    score = 8.0 if i % 2 == 0 else 3.0
                    status = "accepted" if i % 2 == 0 else "rejected"
                    await conn.execute(
                        text(insert_sql),
                        {
                            "t": topic_id,
                            "url": f"https://example.com/item-{i}",
                            "hash": uuid.uuid4().hex,
                            "title": f"Item {i}",
                            "score": score,
                            "status": status,
                        },
                    )

        asyncio.run(_insert())
    finally:
        import asyncio

        asyncio.run(engine.dispose())
    return topic_id


def test_feed_paginates_accepted_only_with_cursor(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    topic_id = _create_topic_with_items(client, auth_headers, 6)

    page1 = client.get(f"/api/v1/topics/{topic_id}/items?limit=2", headers=auth_headers).json()
    assert len(page1["items"]) == 2  # accepted 只有 3 条,limit=2
    assert page1["next_cursor"] is not None

    ids_page1 = [item["id"] for item in page1["items"]]
    assert ids_page1 == sorted(ids_page1, reverse=True)  # id 倒序

    page2 = client.get(
        f"/api/v1/topics/{topic_id}/items?limit=2&cursor={page1['next_cursor']}",
        headers=auth_headers,
    ).json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
    assert page2["items"][0]["id"] < ids_page1[-1]

    # min_score 过滤:低分条目(rejected 3.0)不在,高分 accepted 全可见
    high = client.get(f"/api/v1/topics/{topic_id}/items?min_score=7", headers=auth_headers).json()
    assert len(high["items"]) == 3
    assert all(item["score"] >= 7 for item in high["items"])


def test_feed_query_uses_index(client: TestClient, auth_headers: dict[str, str]) -> None:
    topic_id = _create_topic_with_items(client, auth_headers, 3)

    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        import asyncio

        async def _explain() -> str:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text(
                        "EXPLAIN SELECT * FROM items WHERE topic_id = :t "
                        "AND status = 'accepted' AND id < 1000000 "
                        "ORDER BY id DESC LIMIT 20"
                    ),
                    {"t": topic_id},
                )
                return "\n".join(row[0] for row in rows)

        plan = asyncio.run(_explain())
        assert "ix_items_topic_id" in plan, plan
    finally:
        import asyncio

        asyncio.run(engine.dispose())


def test_feed_cross_user_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    topic_id = _create_topic_with_items(client, auth_headers, 1)

    other_email = f"feed2-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": other_email, "password": "s3cret-password"})
    other = client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "s3cret-password"}
    ).json()

    resp = client.get(
        f"/api/v1/topics/{topic_id}/items",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"
