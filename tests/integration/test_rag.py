"""已读内容检索(RAG)集成测试:run → 嵌入落库 → 语义检索与跨用户隔离。

标记 integration:CI 使用 pgvector 镜像起 PostgreSQL;嵌入以假件生成。
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
from tradewinds.tools.base import CandidateItem

pytestmark = pytest.mark.integration

MARKER = uuid.uuid4().hex[:8]


class FakePlanner:
    async def compile(self, description: str, cadence: Any) -> Any:
        from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan

        return RetrievalPlan.model_validate(
            {
                "keywords": ["agent", "quant"],
                "sources": ["arxiv"],
                "arxiv_categories": [],
                "github": None,
                "window_days": 7,
                "relevance_criteria": ["相关"],
            }
        )


class FakeSourceClient:
    name = "arxiv"

    def __init__(self, urls: list[str]) -> None:
        self._urls = urls

    async def search(
        self, plan: Any, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        return [
            CandidateItem(
                source="arxiv",
                url=url,
                title=f"Paper {url}",
                raw_content="content",
                published_at=datetime.now(UTC),
            )
            for url in self._urls
        ]


class FakeRunner:
    def __init__(self, urls: list[str]) -> None:
        self._urls = urls

    async def run(self, prompt: str, response_model: Any, **kwargs: Any) -> Any:
        if response_model is AnalystOutput:
            return AnalystOutput(
                items=[ItemScore(url=url, score=8.0, cluster_key="k") for url in self._urls]
            )
        if response_model is ItemDigest:
            return ItemDigest(summary="s", reason="r")
        raise AssertionError(response_model)  # pragma: no cover


class FakeEmbedder:
    """确定性假嵌入:按文本 hash 映射到 4 维单位向量,保证同文本同向量。"""

    model = "fake-embedding"

    async def embed(self, text: str) -> list[float]:
        digest = sum(text.encode("utf-8")) % 4
        return [1.0 if i == digest else 0.0 for i in range(4)]


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        app = test_client.app
        urls = [f"https://example.com/{MARKER}-{i}" for i in range(2)]
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([FakeSourceClient(urls)])
        app.state.analyst = Analyst(runner=FakeRunner(urls))  # type: ignore[arg-type]
        app.state.editor = Editor(runner=FakeRunner(urls))  # type: ignore[arg-type]
        app.state.embedder = FakeEmbedder()
        yield test_client


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"rag-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_run_generates_embeddings_and_search_returns_own_items(client: TestClient) -> None:
    headers = _auth_headers(client)
    topic_id = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "RAG 主题", "description": "d", "cadence": "daily"},
    ).json()["topic"]["id"]
    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text

    # 嵌入落库断言
    import asyncio

    async def _embedding_count() -> int:
        engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(text("SELECT COUNT(*) FROM item_embeddings"))
                return int(rows.scalar_one())
        finally:
            await engine.dispose()

    assert asyncio.run(_embedding_count()) == 2

    # 检索端点:返回本人条目
    hits = client.get("/api/v1/items/search", params={"q": "agent"}, headers=headers).json()
    assert len(hits) == 2
    assert all(hit["url"].startswith(f"https://example.com/{MARKER}") for hit in hits)
    assert hits == sorted(hits, key=lambda h: h["distance"])

    # 跨用户隔离:另一用户检索不到任何结果
    other_email = f"rag2-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": other_email, "password": "s3cret-password"})
    other = client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "s3cret-password"}
    ).json()
    other_hits = client.get(
        "/api/v1/items/search",
        params={"q": "agent"},
        headers={"Authorization": f"Bearer {other['access_token']}"},
    ).json()
    assert other_hits == []


def test_search_disabled_without_embedder(client: TestClient) -> None:
    headers = _auth_headers(client)
    saved = client.app.state.embedder
    client.app.state.embedder = None
    try:
        resp = client.get("/api/v1/items/search", params={"q": "x"}, headers=headers)
        assert resp.status_code == 404
    finally:
        client.app.state.embedder = saved
