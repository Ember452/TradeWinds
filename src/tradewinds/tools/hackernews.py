"""Hacker News 客户端:Algolia Search API,按时间过滤讨论与链接。"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.tools.base import CandidateItem, RateLimiter, is_seen
from tradewinds.tools.http import fetch_text

_API_URL = "https://hn.algolia.com/api/v1/search"
_RAW_CONTENT_MAX = 4000


class HackerNewsClient:
    name = "hackernews"

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

        cutoff = int((datetime.now(UTC) - timedelta(days=plan.window_days)).timestamp())
        params: dict[str, Any] = {
            "query": " OR ".join(plan.keywords),
            "tags": "story",
            "hitsPerPage": self._max_results,
            "numericFilters": f"created_at_i>{cutoff}",
        }
        body = await fetch_text(self._limiter, self._client, _API_URL, params=params)
        return self._parse(body, topic_id=topic_id, seen_hashes=seen_hashes)

    def _parse(self, body: str, *, topic_id: int, seen_hashes: set[str]) -> list[CandidateItem]:
        import json

        try:
            data = json.loads(body)
            hits = data["hits"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceError("hackernews 响应解析失败") from exc

        items: list[CandidateItem] = []
        for hit in hits:
            object_id = str(hit.get("objectID", ""))
            title = normalize_whitespace(str(hit.get("title") or ""))
            if not object_id or not title:
                continue
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            if is_seen(url, topic_id, seen_hashes):
                continue
            story_text = normalize_whitespace(str(hit.get("story_text") or ""))
            points = hit.get("points")
            context = f"{points} points" if points is not None else "HN discussion"
            raw = f"{context}. {story_text}" if story_text else context
            items.append(
                CandidateItem(
                    source=self.name,
                    url=url,
                    title=title,
                    raw_content=truncate_text(raw, _RAW_CONTENT_MAX),
                    published_at=_parse_dt(hit.get("created_at")),
                )
            )
        return items


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
