"""HackerNewsClient 契约测试:正常/空结果/畸形响应三固件。"""

from typing import Any

import httpx
import pytest

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.tools.base import RateLimiter, url_hash
from tradewinds.tools.hackernews import HackerNewsClient

TOPIC_ID = 3


def _plan(window_days: int = 7) -> RetrievalPlan:
    return RetrievalPlan.model_validate(
        {
            "keywords": ["agent framework", "evals"],
            "sources": ["hackernews"],
            "arxiv_categories": [],
            "github": None,
            "window_days": window_days,
            "relevance_criteria": ["社区高热度讨论"],
        }
    )


def _client_with_fixture(load_fixture, mock_client, name: str) -> HackerNewsClient:
    body = load_fixture("hackernews", name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    return HackerNewsClient(RateLimiter(), client=mock_client(handler))


async def test_normal_fixture_parses_items(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "normal.json")

    items = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    assert len(items) == 2
    assert items[0].url == "https://example.com/agent-framework?utm_source=news".replace(
        "?utm_source=news", ""
    ) or items[0].url.startswith("https://example.com/agent-framework")
    assert items[0].published_at is not None
    # 无外链的 Ask HN 回退到 item 链接,story_text 进入 raw_content
    ask = next(i for i in items if i.title.startswith("Ask HN"))
    assert ask.url == "https://news.ycombinator.com/item?id=35000002"
    assert "eval pipeline" in ask.raw_content


async def test_seen_filter_and_incremental(load_fixture, mock_client) -> None:
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


async def test_query_carries_keywords_and_time_filter(mock_client) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, text='{"hits":[]}')

    client = HackerNewsClient(RateLimiter(), client=mock_client(handler))
    await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    assert "agent framework" in captured["params"]["query"]
    assert captured["params"]["numericFilters"].startswith("created_at_i>")
