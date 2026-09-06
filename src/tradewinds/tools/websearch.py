"""Web 通用搜索客户端:DuckDuckGo HTML 端点,补齐 SourceName.web。

解析依赖 DDG 稳定的结果结构(result__a 标题链接 + result__snippet 摘要,
跳转链接经 uddg 参数承载真实 URL);零结果属正常情形返回空列表,
不作为 SourceError 降级。线上结构变化以契约测试固件守护。
"""

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import httpx

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.tools.base import CandidateItem, RateLimiter, is_seen
from tradewinds.tools.http import fetch_text

_ENDPOINT = "https://html.duckduckgo.com/html/"
_SNIPPET_MAX = 1000
_TITLE_CLASS = "result__a"
_SNIPPET_CLASS = "result__snippet"


class _ResultParser(HTMLParser):
    """按出现顺序配对标题链接与摘要;广告(y.js)与非结果链接丢弃。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[tuple[str, str, str]] = []  # (title, url, snippet)
        self._capture: str | None = None  # 正在采集的字段名
        self._buffer: list[str] = []
        self._current_title: str | None = None
        self._current_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        classes = (attrs_map.get("class") or "").split()
        href = attrs_map.get("href") or ""
        if _TITLE_CLASS in classes:
            url = _unwrap_href(href)
            self._flush()
            if url is None:  # 广告等非结果链接,内容整体丢弃
                return
            self._current_title = ""
            self._current_url = url
            self._capture = "title"
        elif _SNIPPET_CLASS in classes and self._current_url is not None:
            self._capture = "snippet"

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._capture is None:
            return
        text = "".join(self._buffer)
        self._buffer = []
        capture = self._capture
        self._capture = None
        if capture == "title":
            self._current_title = normalize_whitespace(text)
        else:
            self._flush(snippet=normalize_whitespace(text))

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self, snippet: str = "") -> None:
        """收尾当前结果:标题非空才计入,并复位采集状态。"""
        if self._current_url is not None and self._current_title:
            self.results.append((self._current_title, self._current_url, snippet))
        self._current_title = None
        self._current_url = None
        self._buffer = []
        self._capture = None


def _unwrap_href(href: str) -> str | None:
    """解开 DDG 跳转链接(//duckduckgo.com/l/?uddg=<encoded>)取真实 URL;
    广告(/y.js)与站内链接返回 None。"""
    if "/y.js" in href:
        return None
    if "uddg=" not in href:
        return None if href.startswith("/") or "duckduckgo.com" in href else href
    params = parse_qs(urlsplit(href).query)
    unwrapped = params.get("uddg", [""])[0]
    return unwrapped or None


def parse_results(html: str, *, max_results: int) -> list[tuple[str, str, str]]:
    parser = _ResultParser()
    parser.feed(html)
    parser.close()
    return parser.results[:max_results]


class WebSearchClient:
    name = "web"

    def __init__(
        self, limiter: RateLimiter, client: httpx.AsyncClient | None = None, max_results: int = 8
    ) -> None:
        self._limiter = limiter
        self._client = client if client is not None else httpx.AsyncClient(timeout=30)
        self._max_results = max_results

    async def search(
        self, plan: RetrievalPlan, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        if self.name not in [s.value for s in plan.sources]:
            return []

        # DDG 对无浏览器 UA 的请求拒答概率高,携带常规 UA
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        body = await fetch_text(
            self._limiter,
            self._client,
            _ENDPOINT,
            params={"q": " ".join(plan.keywords)},
            headers=headers,
        )
        items: list[CandidateItem] = []
        for title, url, snippet in parse_results(body, max_results=self._max_results):
            if is_seen(url, topic_id, seen_hashes):
                continue
            items.append(
                CandidateItem(
                    source=self.name,
                    url=url,
                    title=title,
                    raw_content=truncate_text(snippet, _SNIPPET_MAX),
                    published_at=None,
                )
            )
        return items
