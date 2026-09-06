"""RSS 客户端契约测试:RSS 2.0 / Atom / 畸形三固件(MockTransport,零网络)。"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.tools.base import RateLimiter, url_hash
from tradewinds.tools.rss import RssClient, parse_feed

RSS20 = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example Blog</title>
  <item>
    <title>  Post One
      about agents </title>
    <link>https://blog.example/post-1?utm_source=rss</link>
    <pubDate>Mon, 01 Sep 2026 10:00:00 GMT</pubDate>
    <description>First post body.</description>
  </item>
  <item>
    <title>Old Post</title>
    <link>https://blog.example/old</link>
    <pubDate>Mon, 01 Jan 2020 10:00:00 GMT</pubDate>
    <description>Outside window.</description>
  </item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>  Atom Entry
      One </title>
    <link rel="alternate" href="https://atom.example/entry-1"/>
    <published>2026-09-04T08:00:00Z</published>
    <summary>Atom body.</summary>
  </entry>
  <entry>
    <title>No link entry</title>
    <summary>Should be skipped.</summary>
  </entry>
</feed>"""

MALFORMED = "<rss><channel><item><title>broken"

TOPIC_ID = 11


def _plan(window_days: int = 31) -> RetrievalPlan:
    return RetrievalPlan.model_validate(
        {
            "keywords": ["agent", "quant"],
            "sources": ["arxiv"],
            "arxiv_categories": [],
            "github": None,
            "window_days": window_days,
            "relevance_criteria": ["相关"],
        }
    )


def _client(body: str) -> RssClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    return RssClient(
        RateLimiter(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        feed_id=3,
        url="https://feeds.example/x",
    )


def test_parse_rss20_normalizes_and_filters_window() -> None:
    entries = parse_feed(RSS20)

    assert len(entries) == 2
    assert entries[0].title == "Post One about agents"
    assert entries[0].url == "https://blog.example/post-1?utm_source=rss"
    assert entries[0].published_at == datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def test_parse_atom_entries() -> None:
    entries = parse_feed(ATOM)

    assert len(entries) == 1  # 无 link 的条目被跳过
    assert entries[0].title == "Atom Entry One"
    assert entries[0].published_at == datetime(2026, 9, 4, 8, 0, tzinfo=UTC)


def test_parse_malformed_raises_source_error() -> None:
    with pytest.raises(SourceError):
        parse_feed(MALFORMED)


async def test_client_search_filters_window_and_seen() -> None:
    client = _client(RSS20)

    items = await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=set())
    assert len(items) == 1
    assert items[0].source == "rss:3"

    seen = {f"{TOPIC_ID}:{url_hash(items[0].url, TOPIC_ID)}"}
    assert await client.search(_plan(), topic_id=TOPIC_ID, seen_hashes=seen) == []


async def test_client_window_days_filters_stale() -> None:
    client = _client(RSS20)

    # 窗口收窄到 30 天:2020 年的旧文被过滤
    items = await client.search(_plan(window_days=30), topic_id=TOPIC_ID, seen_hashes=set())

    assert [i.title for i in items] == ["Post One about agents"]
    assert items[0].published_at is not None
    assert items[0].published_at > datetime.now(UTC) - timedelta(days=30)
