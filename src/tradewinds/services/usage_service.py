"""LLM 用量服务:落库 recorder 与按日聚合查询。

配额幂等说明:用量在 StructuredRunner 成功返回后记录一次;
管道重复 run 因指纹去重不会再次调用 LLM,任务重试(重跑)也只对
新条目计费,不存在重复扣减。
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.agents.orchestrator.llm import ModelTier, Usage
from tradewinds.models.llm_usage import LLMUsageRecord


class SessionUsageRecorder:
    """落库实现:每次记录自建短会话,与请求/任务会话解耦。"""

    def __init__(self, session_factory: Any) -> None:
        self._factory = session_factory

    async def record(self, user_id: int, role: str, tier: ModelTier, usage: Usage) -> None:
        async with self._factory() as session:
            session.add(
                LLMUsageRecord(
                    user_id=user_id,
                    role=role,
                    tier=tier.value,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )
            )
            await session.commit()


@dataclass(frozen=True)
class DailyUsageRow:
    role: str
    tier: str
    total_tokens: int
    calls: int


async def record_usage(
    session: AsyncSession, user_id: int, role: str, tier: str, usage: Usage
) -> None:
    """直接以现有会话写一条用量(供测试与脚本使用)。"""
    session.add(
        LLMUsageRecord(
            user_id=user_id,
            role=role,
            tier=tier,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
    )
    await session.commit()


async def daily_usage(session: AsyncSession, user_id: int, *, day: date) -> list[DailyUsageRow]:
    """按日聚合(UTC):角色 x 档位 的 token 合计与调用次数。"""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    rows = await session.execute(
        select(
            LLMUsageRecord.role,
            LLMUsageRecord.tier,
            func.sum(LLMUsageRecord.total_tokens),
            func.count(),
        )
        .where(LLMUsageRecord.user_id == user_id)
        .where(LLMUsageRecord.created_at >= start)
        .where(LLMUsageRecord.created_at < end)
        .group_by(LLMUsageRecord.role, LLMUsageRecord.tier)
    )
    return [
        DailyUsageRow(role=row[0], tier=row[1], total_tokens=int(row[2]), calls=int(row[3]))
        for row in rows.all()
    ]


def utc_now() -> datetime:
    """隔离时钟,便于测试。"""
    return datetime.now(UTC)
