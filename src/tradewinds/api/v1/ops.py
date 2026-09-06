"""运维指标汇总:阶段 0 三大核心指标(队列/LLM 成本/业务量)的查询出口。

鉴权:X-Ops-Token 对比 Settings.ops_token;未配置 token 时接口关闭(404,
不泄露存在性)。供外部告警/监控脚本拉取,阈值见 docs/runbook.md。
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.api.deps import get_db
from tradewinds.core.config import Settings, get_settings
from tradewinds.core.exceptions import AuthError, NotFoundError
from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.llm_usage import LLMUsageRecord
from tradewinds.models.push_log import PushLog
from tradewinds.models.topic import Topic, TopicStatus
from tradewinds.models.user import User

router = APIRouter(prefix="/ops", tags=["ops"])

_QUEUES = ("default", "pipeline", "push")


def require_ops_token(request: Request, settings: Settings = Depends(get_settings)) -> None:
    token = settings.ops_token
    if not token:
        raise NotFoundError("未启用")
    if request.headers.get("X-Ops-Token") != token:
        raise AuthError("无效的运维凭证")


async def _queue_backlog(redis: Any) -> dict[str, int]:
    backlog: dict[str, int] = {}
    for queue in _QUEUES:
        try:
            backlog[queue] = int(await redis.llen(queue))
        except Exception:
            backlog[queue] = -1
    return backlog


@router.get("/summary", dependencies=[Depends(require_ops_token)])
async def ops_summary(request: Request, session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h = now - timedelta(days=1)

    token_rows = await session.execute(
        select(
            LLMUsageRecord.tier,
            func.sum(LLMUsageRecord.total_tokens),
            func.count(),
        )
        .where(LLMUsageRecord.created_at >= day_start)
        .group_by(LLMUsageRecord.tier)
    )
    llm_today = {
        tier: {"total_tokens": int(total), "calls": int(calls)}
        for tier, total, calls in token_rows.all()
    }

    users = await session.scalar(select(func.count()).select_from(User))
    topics = await session.scalar(select(func.count()).select_from(Topic))
    topics_active = await session.scalar(
        select(func.count()).select_from(Topic).where(Topic.status == TopicStatus.active)
    )
    items_24h = await session.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.created_at >= last_24h, Item.status == ItemStatus.accepted)
    )

    push_rows = await session.execute(
        select(PushLog.status, func.count())
        .where(PushLog.created_at >= day_start)
        .group_by(PushLog.status)
    )
    push_today = {
        (status.value if hasattr(status, "value") else str(status)): int(n)
        for status, n in push_rows.all()
    }

    return {
        "generated_at": now.isoformat(),
        "queue_backlog": await _queue_backlog(request.app.state.redis),
        "llm_usage_today": llm_today,
        "counts": {
            "users": int(users or 0),
            "topics": int(topics or 0),
            "topics_active": int(topics_active or 0),
            "items_accepted_24h": int(items_24h or 0),
        },
        "push_today": push_today,
    }
