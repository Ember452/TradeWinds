"""自定义 RSS 源集成测试:提交(健康校验)→ run 管道 → 条目入库;坏源降级。

标记 integration:CI 起 PostgreSQL/Redis service 运行;HTTP 用
MockTransport 假件(替换 app.state.http_client)。
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.item_digest import ItemDigest
from tradewinds.agents.schemas.scored_item import AnalystOutput, ItemScore
from tradewinds.api.app import create_app
from tradewinds.tools.base import CandidateItem, is_seen

pytestmark = pytest.mark.integration

MARKER = uuid.uuid4().hex[:8]

GOOD_FEED = f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Custom</title>
  <item>
    <title>Custom Post {MARKER}</title>
    <link>https://custom.example/{MARKER}-post</link>
    <pubDate>Sat, 05 Sep 2026 10:00:00 GMT</pubDate>
    <description>Custom body.</description>
  </item>
</channel></rss>"""

BROKEN_FEED = "<rss><channel><item><title>broken"


def _routing_client() -> httpx.AsyncClient:
    """按 URL 分流:好源返回有效 RSS,坏源返回畸形内容。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if "good" in str(request.url):
            return httpx.Response(200, text=GOOD_FEED)
        return httpx.Response(200, text=BROKEN_FEED)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class FakePlanner:
    async def compile(self, description: str, cadence: Any) -> Any:
        from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan

        return RetrievalPlan.model_validate(
            {
                "keywords": ["agent", "quant"],
                "sources": ["arxiv"],
                "arxiv_categories": [],
                "github": None,
                "window_days": 31,
                "relevance_criteria": ["相关"],
            }
        )


class FakeSourceClient:
    name = "arxiv"

    async def search(
        self, plan: Any, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        candidates = [
            CandidateItem(
                source="arxiv",
                url=f"https://example.com/{MARKER}-paper",
                title="Paper",
                raw_content="content",
                published_at=datetime.now(UTC),
            )
        ]
        return [c for c in candidates if not is_seen(c.url, topic_id, seen_hashes)]


class FakeRunner:
    async def run(
        self,
        prompt: str,
        response_model: Any,
        *,
        model: Any,
        role: str | None = None,
        user_id: int | None = None,
    ) -> Any:
        if response_model is AnalystOutput:
            # 默认源与自定义源条目都评分,两条都进 Feed
            return AnalystOutput(
                items=[
                    ItemScore(
                        url=f"https://example.com/{MARKER}-paper", score=8.0, cluster_key="p"
                    ),
                    ItemScore(
                        url=f"https://custom.example/{MARKER}-post", score=7.0, cluster_key="c"
                    ),
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
        app.state.http_client = _routing_client()
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([FakeSourceClient()])
        app.state.analyst = Analyst(runner=FakeRunner())  # type: ignore[arg-type]
        app.state.editor = Editor(runner=FakeRunner())  # type: ignore[arg-type]
        yield test_client


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"feed-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_custom_feed_flow(client: TestClient) -> None:
    headers = _auth_headers(client)
    topic_id = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "自定义源主题", "description": "d", "cadence": "daily"},
    ).json()["topic"]["id"]

    # 提交好源与坏源
    good = client.post(
        f"/api/v1/topics/{topic_id}/feeds",
        headers=headers,
        json={"url": f"https://feeds.example/good-{MARKER}"},
    )
    assert good.status_code == 201, good.text
    assert good.json()["status"] == "healthy"

    broken = client.post(
        f"/api/v1/topics/{topic_id}/feeds",
        headers=headers,
        json={"url": f"https://feeds.example/broken-{MARKER}"},
    )
    assert broken.status_code == 422
    assert broken.json()["code"] == "invalid_feed"

    # 重复提交 → 409
    dup = client.post(
        f"/api/v1/topics/{topic_id}/feeds",
        headers=headers,
        json={"url": f"https://feeds.example/good-{MARKER}"},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "duplicate_feed"

    # run 管道:自定义源条目与默认源条目都入库
    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text

    feed_page = client.get(f"/api/v1/topics/{topic_id}/items", headers=headers).json()
    urls = [item["url"] for item in feed_page["items"]]
    assert f"https://custom.example/{MARKER}-post" in urls
    assert f"https://example.com/{MARKER}-paper" in urls

    # 删除自定义源
    feed_id = good.json()["id"]
    deleted = client.delete(f"/api/v1/topics/{topic_id}/feeds/{feed_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/topics/{topic_id}/feeds", headers=headers).json() == []
