"""Retriever 并发检索测试:合并各源、单源故障降级不上抛。"""

from typing import Any

from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.core.exceptions import SourceError
from tradewinds.tools.base import CandidateItem

PLAN = RetrievalPlan.model_validate(
    {
        "keywords": ["agent", "quant"],
        "sources": ["arxiv", "hackernews", "github"],
        "arxiv_categories": ["cs.AI"],
        "github": None,
        "window_days": 7,
        "relevance_criteria": ["相关"],
    }
)


def _item(source: str, url: str) -> CandidateItem:
    return CandidateItem(source=source, url=url, title=f"title-{url}", raw_content="content")


class FakeClient:
    def __init__(self, name: str, items: list[CandidateItem] | Exception) -> None:
        self.name = name
        self._items = items
        self.calls: list[dict[str, Any]] = []

    async def search(
        self, plan: RetrievalPlan, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        self.calls.append({"topic_id": topic_id, "seen": set(seen_hashes)})
        if isinstance(self._items, Exception):
            raise self._items
        return self._items


async def test_collect_merges_all_sources() -> None:
    retriever = Retriever(
        [
            FakeClient("arxiv", [_item("arxiv", "https://a.example/1")]),
            FakeClient("hackernews", [_item("hackernews", "https://h.example/2")]),
        ]
    )

    result = await retriever.collect(PLAN, topic_id=1, seen_hashes=set())

    assert [i.url for i in result.items] == ["https://a.example/1", "https://h.example/2"]
    assert result.degraded == []


async def test_single_source_failure_degrades_but_others_succeed() -> None:
    retriever = Retriever(
        [
            FakeClient("arxiv", SourceError("arxiv 挂了")),
            FakeClient("github", [_item("github", "https://g.example/1")]),
        ]
    )

    result = await retriever.collect(PLAN, topic_id=1, seen_hashes=set())

    assert [i.url for i in result.items] == ["https://g.example/1"]
    assert len(result.degraded) == 1
    assert result.degraded[0].source == "arxiv"
    assert "挂了" in result.degraded[0].reason


async def test_collect_passes_topic_id_and_seen_hashes() -> None:
    arxiv = FakeClient("arxiv", [])
    retriever = Retriever([arxiv])

    await retriever.collect(PLAN, topic_id=42, seen_hashes={"42:abc"})

    assert arxiv.calls[0]["topic_id"] == 42
    assert arxiv.calls[0]["seen"] == {"42:abc"}


async def test_collect_runs_sources_concurrently() -> None:
    import asyncio
    import time

    class SlowClient(FakeClient):
        async def search(self, plan, *, topic_id, seen_hashes):
            await asyncio.sleep(0.1)
            return []

    start = time.monotonic()
    retriever = Retriever([SlowClient("arxiv", []), SlowClient("github", [])])
    await retriever.collect(PLAN, topic_id=1, seen_hashes=set())

    assert time.monotonic() - start < 0.19  # 并发 ~0.1s,串行 ~0.2s
