"""跨会话记忆集成测试:点击 → 偏好画像 → 注入评分上下文。

标记 integration:CI 起 PostgreSQL/Redis service 运行;管道组件以假件
替换,FakeRunner 捕获 prompt 以断言画像注入。
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

    def __init__(self, url: str) -> None:
        self._url = url

    async def search(
        self, plan: Any, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        return [
            CandidateItem(
                source="arxiv",
                url=self._url,
                title=f"Paper {self._url}",
                raw_content="content",
                published_at=datetime.now(UTC),
            )
        ]


class FakeRunner:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def run(self, prompt: str, response_model: Any, **kwargs: Any) -> Any:
        if response_model is AnalystOutput:
            self.prompts.append(prompt)
            # 按条目 URL 给分,保证 accepted
            urls = [
                line.split("URL: ")[1].split("\n")[0]
                for line in prompt.splitlines()
                if "URL: " in line
            ]
            return AnalystOutput(
                items=[
                    ItemScore(url=url, score=9.0, cluster_key=f"cluster-{MARKER}") for url in urls
                ]
            )
        if response_model is ItemDigest:
            return ItemDigest(summary="s", reason="r")
        raise AssertionError(response_model)  # pragma: no cover


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        app = test_client.app
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([FakeSourceClient(f"https://example.com/{MARKER}-a")])
        app.state.analyst = Analyst(runner=FakeRunner())  # type: ignore[arg-type]
        app.state.editor = Editor(runner=FakeRunner())  # type: ignore[arg-type]
        yield test_client


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"pref-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _click_count(database_url: str, user_email_suffix: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM item_clicks c "
                    "JOIN users u ON u.id = c.user_id WHERE u.email LIKE :suffix"
                ),
                {"suffix": f"%{user_email_suffix}%"},
            )
            return int(rows.scalar_one())
    finally:
        await engine.dispose()


def test_click_is_idempotent_and_feeds_preference(client: TestClient) -> None:
    import asyncio

    suffix = f"pref-{uuid.uuid4().hex[:8]}"
    email = f"{suffix}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "s3cret-password"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    # 主题 A:跑一次产生条目
    topic_a = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "主题 A", "description": "d", "cadence": "daily"},
    ).json()["topic"]["id"]
    run = client.post(f"/api/v1/topics/{topic_a}/run", headers=headers)
    assert run.status_code == 200, run.text
    items = client.get(f"/api/v1/topics/{topic_a}/items?limit=5", headers=headers).json()["items"]
    assert items, "应有 accepted 条目"

    # 重复点击两次 → 幂等,只记一条
    for _ in range(2):
        clicked = client.post(f"/api/v1/items/{items[0]['id']}/click", headers=headers)
        assert clicked.status_code == 204, clicked.text
    assert asyncio.run(_click_count(os.environ["TRADEWINDS_DATABASE_URL"], suffix)) == 1

    # 主题 B:同用户再建主题并 run,评分 prompt 应包含点击产生的偏好
    runner: FakeRunner = client.app.state.analyst._runner
    runner.prompts.clear()
    client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "主题 B", "description": "d", "cadence": "daily"},
    )
    topics = client.get("/api/v1/topics", headers=headers).json()
    topic_b = next(t["id"] for t in topics if t["name"] == "主题 B")
    run_b = client.post(f"/api/v1/topics/{topic_b}/run", headers=headers)
    assert run_b.status_code == 200, run_b.text

    assert runner.prompts, "主题 B 的评分应被调用"
    assert "用户历史偏好" in runner.prompts[0]
    assert f"cluster-{MARKER}" in runner.prompts[0]

    # 跨用户隔离:另一个用户看不到别人的主题(归属校验路径已覆盖,这里复核 404 语义)
    other_email = f"pref2-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": other_email, "password": "s3cret-password"})
    other = client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "s3cret-password"}
    ).json()
    resp = client.get(
        f"/api/v1/topics/{topic_a}/items",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert resp.status_code == 404
