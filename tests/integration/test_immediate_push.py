"""即时推送集成测试:阈值触发、24h 聚类抑制、重复不重推。

标记 integration:CI 起 PostgreSQL/Redis service 运行;管道组件与
邮件渠道以假件替换(渠道未配置 → 投递记 skipped)。
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.item_digest import ItemDigest
from tradewinds.agents.schemas.scored_item import AnalystOutput, ItemScore
from tradewinds.api.app import create_app
from tradewinds.tasks.celery_app import celery_app
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

    async def search(
        self, plan: Any, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        return [
            CandidateItem(
                source="arxiv",
                url=f"https://example.com/{MARKER}-{i}",
                title=f"Paper {i}",
                raw_content="content",
                published_at=datetime.now(UTC),
            )
            for i in range(3)
        ]


class FakeRunner:
    async def run(self, prompt: str, response_model: Any, *, model: Any) -> Any:
        if response_model is AnalystOutput:
            # item-0 与 item-1 同聚类且超阈值;item-2 低于即时阈值但仍 accepted
            return AnalystOutput(
                items=[
                    ItemScore(url=f"https://example.com/{MARKER}-0", score=9.0, cluster_key="hot"),
                    ItemScore(url=f"https://example.com/{MARKER}-1", score=8.5, cluster_key="hot"),
                    ItemScore(url=f"https://example.com/{MARKER}-2", score=6.5, cluster_key="warm"),
                ]
            )
        if response_model is ItemDigest:
            return ItemDigest(summary="s", reason="r")
        raise AssertionError(response_model)  # pragma: no cover


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    celery_app.conf.task_always_eager = True
    with TestClient(create_app()) as test_client:
        app = test_client.app
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([FakeSourceClient()])
        app.state.analyst = Analyst(runner=FakeRunner())  # type: ignore[arg-type]
        app.state.editor = Editor(runner=FakeRunner())  # type: ignore[arg-type]
        yield test_client
    celery_app.conf.task_always_eager = False


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"imm-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _push_logs(topic_id: int) -> list[dict[str, Any]]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT push_type, cluster_key, digest_key, status "
                    "FROM push_log WHERE topic_id = :t ORDER BY id"
                ),
                {"t": topic_id},
            )
            return [dict(r._mapping) for r in rows]
    finally:
        await engine.dispose()


def test_immediate_push_threshold_and_cluster_suppression(client: TestClient) -> None:
    import asyncio

    headers = _auth_headers(client)
    topic_id = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "即时推送主题", "description": "d", "cadence": "daily"},
    ).json()["topic"]["id"]

    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text

    logs = asyncio.run(_push_logs(topic_id))
    digests = [log for log in logs if log["push_type"] == "digest"]
    immediates = [log for log in logs if log["push_type"] == "immediate"]

    # 汇总邮件 1 条(3 条 accepted)
    assert len(digests) == 1
    # 即时推送:item-0(9.0)入选;item-1(8.5)同聚类 24h 内被抑制;
    # item-2(6.5)低于阈值不触发
    assert len(immediates) == 1
    assert immediates[0]["cluster_key"] == "hot"
    # 渠道未配置 → 投递记 skipped
    assert immediates[0]["status"] == "skipped"

    # 再跑一次:所有推送幂等,不产生新记录
    client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    logs_again = asyncio.run(_push_logs(topic_id))
    assert len(logs_again) == len(logs)
