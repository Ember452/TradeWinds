"""GithubClient 契约测试:正常/空结果/畸形响应三固件。"""

from typing import Any

import httpx
import pytest

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.tools.base import RateLimiter, url_hash
from tradewinds.tools.github import GithubClient

TOPIC_ID = 5


def _plan(window_days: int = 30) -> RetrievalPlan:
    return RetrievalPlan.model_validate(
        {
            "keywords": ["agent", "quant"],
            "sources": ["github"],
            "arxiv_categories": [],
            "github": {"keywords": ["agent", "framework"], "language": "python", "min_stars": 100},
            "window_days": window_days,
            "relevance_criteria": ["活跃维护的开源项目"],
        }
    )


def _client_with_fixture(load_fixture, mock_client, name: str, **kwargs: Any) -> GithubClient:
    body = load_fixture("github", name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    return GithubClient(RateLimiter(), client=mock_client(handler), **kwargs)


async def test_normal_fixture_parses_and_filters_stale(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "normal.json")

    items = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    # 活跃仓库保留,2026-01-01 推送的陈旧仓库被窗口过滤
    assert len(items) == 1
    assert items[0].title == "example/agent-kit"
    assert "1234 stars" in items[0].raw_content
    assert items[0].published_at is not None


async def test_seen_filter(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "normal.json")
    first = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    seen = {f"{TOPIC_ID}:{url_hash(i.url, TOPIC_ID)}" for i in first}
    second = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=seen)

    assert second == []


async def test_empty_fixture_returns_empty_list(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "empty.json")

    assert await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set()) == []


async def test_malformed_fixture_raises_source_error(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "malformed.json")

    with pytest.raises(SourceError):
        await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())


async def test_query_and_auth_header(mock_client) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, text='{"items":[]}')

    client = GithubClient(RateLimiter(), client=mock_client(handler), token="t0k3n")
    await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    assert "language:python" in captured["params"]["q"]
    assert "stars:>=100" in captured["params"]["q"]
    assert captured["auth"] == "Bearer t0k3n"


async def test_no_github_in_plan_short_circuits(load_fixture, mock_client) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, text="{}")

    plan = _plan()
    plan.sources = [s for s in plan.sources if s.value != "github"]
    plan.github = None
    client = GithubClient(RateLimiter(), client=mock_client(handler))

    assert await client.search(plan, topic_id=TOPIC_ID, seen_hashes=set()) == []
    assert not called
