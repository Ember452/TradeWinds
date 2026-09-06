"""WebSearchClient 契约测试:正常/空结果固件 + 源选择过滤 + 查询参数。

固件按 DuckDuckGo html 端点稳定结构手工构造(本机网络不可达 DDG,
线上结构变化以真实页面回填固件验证)。
"""

from typing import Any

import httpx

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.tools.base import RateLimiter, url_hash
from tradewinds.tools.websearch import WebSearchClient

TOPIC_ID = 7


def _plan(*, sources: list[str] | None = None) -> RetrievalPlan:
    return RetrievalPlan.model_validate(
        {
            "keywords": ["agent framework", "evals"],
            "sources": sources if sources is not None else ["web"],
            "arxiv_categories": [],
            "github": None,
            "window_days": 7,
            "relevance_criteria": ["综合性资讯"],
        }
    )


def _client_with_fixture(load_fixture, mock_client, name: str) -> WebSearchClient:
    body = load_fixture("websearch", name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    return WebSearchClient(RateLimiter(), client=mock_client(handler))


async def test_normal_fixture_parses_items(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "normal.html")

    items = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    # 广告(y.js)与站内链接被丢弃:2 条有机结果 + 1 条无摘要结果
    assert [i.url for i in items] == [
        "https://example.com/guide/agent-frameworks?utm_source=feed",
        "https://papers.example.org/agent-evals",
        "https://docs.example.net/no-snippet",
    ]
    assert items[0].title == "Best Agent Frameworks in 2026"
    assert "agent framework design" in items[0].raw_content
    assert items[2].raw_content == ""
    assert all(i.source == "web" and i.published_at is None for i in items)


async def test_seen_filter_and_incremental(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "normal.html")
    first = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    seen = {f"{TOPIC_ID}:{url_hash(i.url, TOPIC_ID)}" for i in first}
    second = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=seen)

    assert second == []


async def test_empty_fixture_returns_empty_list(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "empty.html")

    assert await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set()) == []


async def test_source_not_selected_returns_empty(mock_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("未选择 web 源时不应发起请求")  # pragma: no cover

    client = WebSearchClient(RateLimiter(), client=mock_client(handler))

    assert await client.search(_plan(sources=["arxiv"]), topic_id=TOPIC_ID, seen_hashes=set()) == []


async def test_query_carries_joined_keywords(mock_client) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, text="")

    client = WebSearchClient(RateLimiter(), client=mock_client(handler))
    await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    assert captured["params"]["q"] == "agent framework evals"


async def test_max_results_caps_items(load_fixture, mock_client) -> None:
    body = load_fixture("websearch", "normal.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    client = WebSearchClient(RateLimiter(), client=mock_client(handler), max_results=1)

    items = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    assert len(items) == 1
