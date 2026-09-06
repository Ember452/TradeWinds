"""Retriever:按计划并发调用各源客户端,单源故障降级不中断。"""

import asyncio

import structlog
from pydantic import BaseModel

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.tools.base import CandidateItem, SourceClient, SourceDegraded

logger = structlog.get_logger(__name__)


class CollectResult(BaseModel):
    items: list[CandidateItem]
    degraded: list[SourceDegraded]


class Retriever:
    def __init__(self, clients: list[SourceClient]) -> None:
        self._clients = clients

    async def collect(
        self, plan: RetrievalPlan, *, topic_id: int, seen_hashes: set[str]
    ) -> CollectResult:
        outcomes = await asyncio.gather(
            *(self._safe_search(client, plan, topic_id, seen_hashes) for client in self._clients)
        )
        items: list[CandidateItem] = []
        degraded: list[SourceDegraded] = []
        for result_items, result_degraded in outcomes:
            items.extend(result_items)
            degraded.extend(result_degraded)
        return CollectResult(items=items, degraded=degraded)

    async def _safe_search(
        self, client: SourceClient, plan: RetrievalPlan, topic_id: int, seen_hashes: set[str]
    ) -> tuple[list[CandidateItem], list[SourceDegraded]]:
        try:
            items = await client.search(plan, topic_id=topic_id, seen_hashes=seen_hashes)
        except Exception as exc:  # 单源故障是可降级的运行态事件,不是程序错误
            logger.warning(
                "source_degraded",
                source=client.name,
                topic_id=topic_id,
                error=str(exc),
            )
            return [], [SourceDegraded(source=client.name, reason=str(exc))]
        return items, []
