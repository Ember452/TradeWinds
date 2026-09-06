"""ArxivClient 契约测试:正常/空结果/畸形响应三固件(MockTransport,零网络)。"""

from typing import Any

import httpx
import pytest

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.tools.arxiv import ArxivClient
from tradewinds.tools.base import RateLimiter, url_hash

TOPIC_ID = 7


def _plan(window_days: int = 30, source: str = "arxiv") -> RetrievalPlan:
    sources = [source] if source else []
    return RetrievalPlan.model_validate(
        {
            "keywords": ["tool use", "agent"],
            "sources": sources,
            "arxiv_categories": ["cs.AI"],
            "github": None,
            "window_days": window_days,
            "relevance_criteria": ["与 Agent 相关"],
        }
    )


def _client_with_fixture(load_fixture, mock_client, name: str) -> ArxivClient:
    body = load_fixture("arxiv", name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    return ArxivClient(RateLimiter(), client=mock_client(handler))


async def test_normal_fixture_parses_and_filters_window(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "normal.xml")

    items = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    # 固件含两条:一条 2026-09-05(窗口内),一条 2026-08-01(30 天窗口外)被过滤
    assert len(items) == 1
    assert items[0].url == "http://arxiv.org/abs/2609.01234v1"
    assert items[0].title == "Tool Use in LLM Agents"
    assert "significant gains" in items[0].raw_content
    assert items[0].published_at is not None


async def test_seen_hashes_filter_out_known_url(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "normal.xml")
    first = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    seen = {f"{TOPIC_ID}:{url_hash(first[0].url, TOPIC_ID)}"}
    second = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=seen)

    assert second == []


async def test_empty_fixture_returns_empty_list(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "empty.xml")

    items = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    assert items == []


async def test_malformed_fixture_raises_source_error(load_fixture, mock_client) -> None:
    client = _client_with_fixture(load_fixture, mock_client, "malformed.xml")

    with pytest.raises(SourceError):
        await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())


async def test_source_not_in_plan_short_circuits(mock_client) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, text="")

    plan = _plan(source="hackernews")
    client = ArxivClient(RateLimiter(), client=mock_client(handler))

    items = await client.search(plan, topic_id=TOPIC_ID, seen_hashes=set())

    assert items == []
    assert not called


async def test_query_includes_categories_and_keywords(load_fixture, mock_client) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, text=load_fixture("arxiv", "empty.xml"))

    client = ArxivClient(RateLimiter(), client=mock_client(handler))
    await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())

    query = captured["params"]["search_query"]
    assert "cat:cs.AI" in query
    assert '"tool use"' in query
