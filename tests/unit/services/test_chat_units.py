"""ChatService 纯函数与并发限流单元测试(引用提取/校验、限流)。"""

import pytest

from tradewinds.core.exceptions import TradeWindsError
from tradewinds.services.chat_service import (
    UserConcurrencyLimiter,
    extract_citations,
    verify_citations,
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


# --- 引用校验:越界编号剔除、持久化只保留实际引用 ---


def test_verify_citations_keeps_valid_and_drops_uncited() -> None:
    citations = [
        {"index": 1, "url": "https://a.example/1"},
        {"index": 2, "url": "https://b.example/2"},
    ]

    cleaned, kept = verify_citations("结论一 [1]。结论二 [2]。补充 [2]。", citations)

    assert cleaned == "结论一 [1]。结论二 [2]。补充 [2]。"
    assert [c["index"] for c in kept] == [1, 2]


def test_verify_citations_strips_out_of_range_markers() -> None:
    citations = [{"index": 1, "url": "https://a.example/1"}]

    cleaned, kept = verify_citations("结论 [1]。幻觉 [9]。", citations)

    assert cleaned == "结论 [1]。幻觉 。"
    assert [c["index"] for c in kept] == [1]


def test_verify_citations_keeps_only_cited_entries() -> None:
    citations = [
        {"index": 1, "url": "https://a.example/1"},
        {"index": 2, "url": "https://b.example/2"},
    ]

    cleaned, kept = verify_citations("只用到了第二个来源 [2]。", citations)

    assert cleaned == "只用到了第二个来源 [2]。"
    assert [c["index"] for c in kept] == [2]


def test_verify_citations_without_markers_persists_empty() -> None:
    citations = [{"index": 1, "url": "https://a.example/1"}]

    cleaned, kept = verify_citations("没有任何引用标记的回答。", citations)

    assert cleaned == "没有任何引用标记的回答。"
    assert kept == []


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
