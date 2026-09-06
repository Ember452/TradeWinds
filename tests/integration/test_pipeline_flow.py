"""管道全链路集成测试:建主题(假 Planner)→ run(假源/假 LLM)→ 断言落库与状态流转。

标记 integration:CI 起 PostgreSQL/Redis service 运行;组件以假件替换 app.state,
因此不访问真实 LLM/信息源。
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.item_digest import ItemDigest
from tradewinds.agents.schemas.scored_item import AnalystOutput, ItemScore
from tradewinds.api.app import create_app
from tradewinds.models.item import ItemStatus
from tradewinds.tools.base import CandidateItem

pytestmark = pytest.mark.integration

FAKE_PLAN = {
    "keywords": ["agent", "framework"],
    "sources": ["arxiv", "github"],
    "arxiv_categories": ["cs.AI"],
    "github": {"keywords": ["agent"], "language": None, "min_stars": None},
    "window_days": 7,
    "relevance_criteria": ["与 Agent 相关"],
}

CANDIDATES = [
    CandidateItem(
        source="arxiv",
        url="https://example.com/paper-a",
        title="Paper A",
        raw_content="relevant content about agents",
        published_at=datetime(2026, 9, 5, tzinfo=UTC),
    ),
    CandidateItem(
        source="arxiv",
        url="https://example.com/paper-b",
        title="Paper B",
        raw_content="marketing noise",
        published_at=datetime(2026, 9, 5, tzinfo=UTC),
    ),
]


class FakePlanner:
    async def compile(self, description: str, cadence: Any) -> Any:
        from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan

        return RetrievalPlan.model_validate(FAKE_PLAN)


class FakeSourceClient:
    name = "arxiv"

    async def search(
        self, plan: Any, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        return CANDIDATES


class FakeRunner:
    """按 response_model 分流:Analyst 输出固定评分,Editor 输出固定摘要。"""

    async def run(self, prompt: str, response_model: Any, *, model: Any) -> Any:
        if response_model is AnalystOutput:
            return AnalystOutput(
                items=[
                    ItemScore(
                        url="https://example.com/paper-a", score=8.5, cluster_key="agent-news"
                    ),
                    ItemScore(url="https://example.com/paper-b", score=2.0, cluster_key="noise"),
                ]
            )
        if response_model is ItemDigest:
            return ItemDigest(summary="摘要内容", reason="推荐理由")
        raise AssertionError(f"unexpected response_model {response_model}")  # pragma: no cover


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        app = test_client.app
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([FakeSourceClient()])
        app.state.analyst = Analyst(runner=FakeRunner())  # type: ignore[arg-type]
        app.state.editor = Editor(runner=FakeRunner())  # type: ignore[arg-type]
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    email = f"pipe-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_topic(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "Agent 动态", "description": "近一周 Agent 新技术", "cadence": "weekly"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _load_items(topic_id: int) -> list[dict]:
    # 独立 engine:asyncpg 连接绑定事件循环,不能复用应用 lifespan 里那个
    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        async with engine.connect() as conn:
            query = (
                "SELECT status, score, cluster_key, summary, reason FROM items WHERE topic_id = :t"
            )
            rows = await conn.execute(text(query), {"t": topic_id})
            return [dict(row._mapping) for row in rows]
    finally:
        await engine.dispose()


def test_create_topic_returns_plan_preview(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    body = _create_topic(client, auth_headers)

    assert body["plan"]["keywords"] == FAKE_PLAN["keywords"]
    assert body["topic"]["cadence"] == "weekly"


def test_run_pipeline_persists_items_with_status_flow(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    topic_id = _create_topic(client, auth_headers)["topic"]["id"]

    resp = client.post(f"/api/v1/topics/{topic_id}/run", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    counts = resp.json()
    assert counts["collected"] == 2
    assert counts["new_items"] == 2
    assert counts["accepted"] == 1
    assert counts["rejected"] == 1
    assert counts["degraded"] == []


def test_run_pipeline_persists_items_and_dedupes_rerun(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    import asyncio

    topic_id = _create_topic(client, auth_headers)["topic"]["id"]

    first = client.post(f"/api/v1/topics/{topic_id}/run", headers=auth_headers).json()
    second = client.post(f"/api/v1/topics/{topic_id}/run", headers=auth_headers).json()

    assert first["new_items"] == 2
    # 重复 run:指纹去重,不产生重复条目,也不重复计数
    assert second["new_items"] == 0
    assert second["accepted"] == 0

    items = asyncio.run(_load_items(topic_id))
    assert len(items) == 2
    by_status = {row["status"]: row for row in items}
    assert ItemStatus("accepted") in by_status
    assert ItemStatus("rejected") in by_status
    accepted = by_status[ItemStatus("accepted")]
    assert accepted["summary"] == "摘要内容"
    assert accepted["reason"] == "推荐理由"
    assert accepted["score"] == 8.5
    assert accepted["cluster_key"] == "agent-news"
    rejected = by_status[ItemStatus("rejected")]
    assert rejected["summary"] is None
    assert rejected["score"] == 2.0


def test_cross_user_topic_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    topic_id = _create_topic(client, auth_headers)["topic"]["id"]

    other_email = f"pipe2-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": other_email, "password": "s3cret-password"})
    other_login = client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "s3cret-password"}
    ).json()
    other_headers = {"Authorization": f"Bearer {other_login['access_token']}"}

    resp = client.get(f"/api/v1/topics/{topic_id}", headers=other_headers)

    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_topic_quota_exceeded_returns_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    from tradewinds.core.config import get_settings

    get_settings.cache_clear()
    os.environ["TRADEWINDS_QUOTA_TOPICS_MAX"] = "1"
    get_settings.cache_clear()
    try:
        first = client.post(
            "/api/v1/topics",
            headers=auth_headers,
            json={"name": "T1", "description": "d1", "cadence": "daily"},
        )
        assert first.status_code == 201
        second = client.post(
            "/api/v1/topics",
            headers=auth_headers,
            json={"name": "T2", "description": "d2", "cadence": "daily"},
        )
        assert second.status_code == 403
        assert second.json()["code"] == "quota_exceeded"
    finally:
        os.environ.pop("TRADEWINDS_QUOTA_TOPICS_MAX", None)
        get_settings.cache_clear()
