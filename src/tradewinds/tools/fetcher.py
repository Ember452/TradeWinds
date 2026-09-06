"""通用网页抓取:GET + 正文提取(标准库 HTMLParser,无重依赖)。

MVP 提取策略:去 script/style,取 <title> 与可见文本;
复杂排版站点精度有限,由 Analyst 阶段的截断与评分兜底。
"""

from html.parser import HTMLParser

import httpx
from pydantic import BaseModel

from tradewinds.core.exceptions import SourceError
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.tools.base import RateLimiter

_TEXT_MAX_CHARS = 8000
_SKIP_TAGS = {"script", "style", "noscript"}


class ExtractedContent(BaseModel):
    url: str
    title: str
    text: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    @property
    def text(self) -> str:
        return " ".join(self._chunks)


class Fetcher:
    name = "fetcher"

    def __init__(self, limiter: RateLimiter, client: httpx.AsyncClient | None = None) -> None:
        self._limiter = limiter
        self._client = (
            client if client is not None else httpx.AsyncClient(timeout=30, follow_redirects=True)
        )

    async def fetch(self, url: str) -> ExtractedContent:
        async def _do() -> httpx.Response:
            try:
                response = await self._client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SourceError(f"抓取失败 {url}:{exc}") from exc
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                raise SourceError(f"不支持的内容类型 {content_type}:{url}")
            return response

        response = await self._limiter.run(_do)

        extractor = _TextExtractor()
        try:
            extractor.feed(response.text)
        except Exception as exc:
            raise SourceError(f"HTML 解析失败 {url}:{exc}") from exc

        return ExtractedContent(
            url=url,
            title=normalize_whitespace(extractor.title) or url,
            text=truncate_text(normalize_whitespace(extractor.text), _TEXT_MAX_CHARS),
        )
