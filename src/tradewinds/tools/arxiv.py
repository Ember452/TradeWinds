"""arXiv 客户端:Atom API,按分类与关键词组合检索最新论文。"""

import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.tools.base import CandidateItem, RateLimiter, is_seen
from tradewinds.tools.http import fetch_text

_ATOM = "{http://www.w3.org/2005/Atom}"
_API_URL = "http://export.arxiv.org/api/query"
_RAW_CONTENT_MAX = 4000


class ArxivClient:
    name = "arxiv"

    def __init__(
        self, limiter: RateLimiter, client: httpx.AsyncClient | None = None, max_results: int = 20
    ) -> None:
        self._limiter = limiter
        self._client = client if client is not None else httpx.AsyncClient(timeout=30)
        self._max_results = max_results

    async def search(
        self, plan: RetrievalPlan, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        if self.name not in [s.value for s in plan.sources]:
            return []

        keywords = " OR ".join(f'all:"{k}"' for k in plan.keywords)
        categories = " OR ".join(f"cat:{c}" for c in plan.arxiv_categories)
        if categories and keywords:
            query = f"({categories}) AND ({keywords})"
        else:
            query = categories or keywords
        if not query:
            return []

        params: dict[str, Any] = {
            "search_query": query,
            "start": 0,
            "max_results": self._max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        body = await fetch_text(self._limiter, self._client, _API_URL, params=params)
        return self._parse(body, topic_id=topic_id, seen_hashes=seen_hashes, plan=plan)

    def _parse(
        self, body: str, *, topic_id: int, seen_hashes: set[str], plan: RetrievalPlan
    ) -> list[CandidateItem]:
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise SourceError("arxiv 响应解析失败") from exc

        cutoff = datetime.now(UTC) - timedelta(days=plan.window_days)
        items: list[CandidateItem] = []
        for entry in root.findall(f"{_ATOM}entry"):
            url = (entry.findtext(f"{_ATOM}id") or "").strip()
            title = normalize_whitespace(entry.findtext(f"{_ATOM}title") or "")
            if not url or not title:
                continue
            published_at = _parse_dt(entry.findtext(f"{_ATOM}published"))
            if published_at is not None and published_at < cutoff:
                continue
            if is_seen(url, topic_id, seen_hashes):
                continue
            summary = normalize_whitespace(entry.findtext(f"{_ATOM}summary") or "")
            items.append(
                CandidateItem(
                    source=self.name,
                    url=url,
                    title=title,
                    raw_content=truncate_text(summary, _RAW_CONTENT_MAX),
                    published_at=published_at,
                )
            )
        return items


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
