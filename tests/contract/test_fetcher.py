"""Fetcher 通用抓取测试:正文提取、非 HTML 拒绝、HTTP 错误转 SourceError。"""

import httpx
import pytest

from tradewinds.core.exceptions import SourceError
from tradewinds.tools.base import RateLimiter
from tradewinds.tools.fetcher import Fetcher

HTML = """
<html><head><title>  My Article
Title </title><script>var x = "noise";</script></head>
<body><style>.a{}</style>
<p>First   paragraph.</p>
<div>Second <b>bold</b> part</div>
</body></html>
"""


def _fetcher(mock_client, body: str, content_type: str = "text/html") -> Fetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": content_type})

    return Fetcher(RateLimiter(), client=mock_client(handler))


async def test_extracts_title_and_visible_text(mock_client) -> None:
    fetcher = _fetcher(mock_client, HTML)

    extracted = await fetcher.fetch("https://example.com/article")

    assert extracted.title == "My Article Title"
    assert "First paragraph." in extracted.text
    assert "Second bold part" in extracted.text
    assert "noise" not in extracted.text  # script 内容被剔除


async def test_non_html_content_rejected(mock_client) -> None:
    fetcher = _fetcher(mock_client, "%PDF-1.4", content_type="application/pdf")

    with pytest.raises(SourceError):
        await fetcher.fetch("https://example.com/doc.pdf")


async def test_http_error_raises_source_error(mock_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope", headers={"content-type": "text/html"})

    fetcher = Fetcher(RateLimiter(), client=mock_client(handler))

    with pytest.raises(SourceError):
        await fetcher.fetch("https://example.com/missing")


async def test_long_text_truncated(mock_client) -> None:
    body = "<html><body>" + "<p>word </p>" * 3000 + "</body></html>"

    extracted = await _fetcher(mock_client, body).fetch("https://example.com/long")

    assert len(extracted.text) <= 8000
