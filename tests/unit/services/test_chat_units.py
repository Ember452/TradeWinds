"""ChatService 纯函数与并发限流单元测试。"""

import pytest

from tradewinds.core.exceptions import TradeWindsError
from tradewinds.services.chat_service import (
    UserConcurrencyLimiter,
    chunk_text,
    extract_citations,
)


def test_extract_citations_dedupes_and_numbers() -> None:
    trace = [
        {"tool": "search_arxiv", "result": "论文A https://a.example/1 摘要..."},
        {"tool": "fetch_page", "result": "正文 https://a.example/1 更多 https://b.example/2. "},
        {"tool": "search_github", "result": "无结果"},
    ]

    citations = extract_citations(trace)

    assert [c["index"] for c in citations] == [1, 2]
    assert citations[0]["url"] == "https://a.example/1"
    assert citations[1]["url"] == "https://b.example/2"


def test_chunk_text_covers_all_content() -> None:
    text = "x" * 250

    chunks = chunk_text(text, size=100)

    assert "".join(chunks) == text
    assert len(chunks) == 3


async def test_limiter_allows_up_to_limit() -> None:
    limiter = UserConcurrencyLimiter(limit=2)

    async with limiter.slot(1), limiter.slot(1):
        pass  # 并发 2 达到上限但不报错


async def test_limiter_rejects_over_limit() -> None:
    limiter = UserConcurrencyLimiter(limit=1)

    async with limiter.slot(1):
        with pytest.raises(TradeWindsError) as exc_info:
            await limiter.slot(1).__aenter__()
    assert exc_info.value.code == "chat_busy"
    assert exc_info.value.status_code == 429


async def test_limiter_releases_after_exit() -> None:
    limiter = UserConcurrencyLimiter(limit=1)

    async with limiter.slot(1):
        pass
    async with limiter.slot(1):
        pass  # 释放后可再次获得
