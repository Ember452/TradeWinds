"""RSS/Atom 通用客户端:用户自定义订阅源进入管道检索范围。

解析用标准库 ElementTree,同时支持 RSS 2.0(channel/item)与 Atom(feed/entry),
不新增依赖;解析失败抛 SourceError 由 Retriever 降级。
"""

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
from pydantic import BaseModel

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.tools.base import CandidateItem, RateLimiter, is_seen
from tradewinds.tools.http import fetch_text

_ATOM = "{http://www.w3.org/2005/Atom}"
_RAW_CONTENT_MAX = 4000


class FeedEntry(BaseModel):
    title: str
    url: str
    published_at: datetime | None
    content: str


def parse_feed(body: str) -> list[FeedEntry]:
    """解析 RSS 2.0 或 Atom 正文;无法识别结构抛 SourceError。"""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise SourceError("订阅源解析失败") from exc

    if root.tag == "rss" or root.tag.startswith("{http://www.itunes.com/dtds/podcast-1.0.dtd}rss"):
        entries = [_entry_from_rss_item(item) for item in root.iter("item")]
    elif root.tag == f"{_ATOM}feed":
        entries = [_entry_from_atom(entry) for entry in root.findall(f"{_ATOM}entry")]
    else:
        raise SourceError("不支持的订阅源格式")

    return [entry for entry in entries if entry is not None]


def _entry_from_rss_item(item: ET.Element) -> FeedEntry | None:
    title = normalize_whitespace(item.findtext("title") or "")
    link = (item.findtext("link") or "").strip()
    if not title or not link:
        return None
    description = normalize_whitespace(item.findtext("description") or "")
    return FeedEntry(
        title=title,
        url=link,
        published_at=_parse_date(item.findtext("pubDate")),
        content=truncate_text(description, _RAW_CONTENT_MAX),
    )


def _entry_from_atom(entry: ET.Element) -> FeedEntry | None:
    title = normalize_whitespace(entry.findtext(f"{_ATOM}title") or "")
    link = ""
    for link_node in entry.findall(f"{_ATOM}link"):
        rel = link_node.get("rel", "alternate")
        href = link_node.get("href") or ""
        if rel == "alternate" and href:
            link = href
            break
    if not title or not link:
        return None
    summary = normalize_whitespace(entry.findtext(f"{_ATOM}summary") or "")
    published = _parse_date(entry.findtext(f"{_ATOM}published")) or _parse_date(
        entry.findtext(f"{_ATOM}updated")
    )
    return FeedEntry(
        title=title,
        url=link,
        published_at=published,
        content=truncate_text(summary, _RAW_CONTENT_MAX),
    )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)  # RFC 822(RSS 2.0)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))  # ISO 8601(Atom)
    except ValueError:
        return None


class RssClient:
    """单个自定义订阅源的客户端;name 形如 rss:<feed_id>,用于降级标注。"""

    def __init__(
        self,
        limiter: RateLimiter,
        client: httpx.AsyncClient,
        *,
        feed_id: int,
        url: str,
    ) -> None:
        self.name = f"rss:{feed_id}"
        self._limiter = limiter
        self._client = client
        self._url = url

    async def search(
        self, plan: RetrievalPlan, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        body = await fetch_text(self._limiter, self._client, self._url)
        entries = parse_feed(body)

        cutoff = datetime.now(UTC) - timedelta(days=plan.window_days)
        items: list[CandidateItem] = []
        for entry in entries:
            if entry.published_at is not None and entry.published_at < cutoff:
                continue
            if is_seen(entry.url, topic_id, seen_hashes):
                continue
            items.append(
                CandidateItem(
                    source=self.name,
                    url=entry.url,
                    title=entry.title,
                    raw_content=entry.content,
                    published_at=entry.published_at,
                )
            )
        return items
