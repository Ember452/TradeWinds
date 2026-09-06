"""GitHub 客户端:Search Repositories API,按关键词/语言/star 过滤仓库。"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.tools.base import CandidateItem, RateLimiter, is_seen
from tradewinds.tools.http import fetch_text

_API_URL = "https://api.github.com/search/repositories"
_RAW_CONTENT_MAX = 4000


class GithubClient:
    name = "github"

    def __init__(
        self,
        limiter: RateLimiter,
        client: httpx.AsyncClient | None = None,
        *,
        token: str | None = None,
        max_results: int = 20,
    ) -> None:
        self._limiter = limiter
        self._client = client if client is not None else httpx.AsyncClient(timeout=30)
        self._token = token
        self._max_results = max_results

    async def search(
        self, plan: RetrievalPlan, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        if self.name not in [s.value for s in plan.sources] or plan.github is None:
            return []

        query = " ".join(plan.github.keywords)
        if plan.github.language:
            query += f" language:{plan.github.language}"
        if plan.github.min_stars is not None:
            query += f" stars:>={plan.github.min_stars}"

        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        params: dict[str, Any] = {"q": query, "sort": "updated", "per_page": self._max_results}

        body = await fetch_text(
            self._limiter, self._client, _API_URL, params=params, headers=headers
        )
        return self._parse(body, topic_id=topic_id, seen_hashes=seen_hashes, plan=plan)

    def _parse(
        self, body: str, *, topic_id: int, seen_hashes: set[str], plan: RetrievalPlan
    ) -> list[CandidateItem]:
        try:
            data = json.loads(body)
            entries = data["items"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceError("github 响应解析失败") from exc

        cutoff = datetime.now(UTC) - timedelta(days=plan.window_days)
        items: list[CandidateItem] = []
        for repo in entries:
            url = repo.get("html_url")
            name = repo.get("full_name")
            if not url or not name:
                continue
            if is_seen(url, topic_id, seen_hashes):
                continue
            pushed_at = _parse_dt(repo.get("pushed_at"))
            if pushed_at is not None and pushed_at < cutoff:
                continue
            description = normalize_whitespace(str(repo.get("description") or ""))
            stars = repo.get("stargazers_count")
            language = repo.get("language")
            raw = (
                f"{name}({stars} stars, {language}): {description}"
                if description
                else f"{name}({stars} stars)"
            )
            items.append(
                CandidateItem(
                    source=self.name,
                    url=url,
                    title=str(name),
                    raw_content=truncate_text(raw, _RAW_CONTENT_MAX),
                    published_at=pushed_at,
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
