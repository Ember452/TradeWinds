"""用量查询端点(内部接口):当前用户按日聚合的 LLM 用量。"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.api.deps import get_current_user, get_db
from tradewinds.models.user import User
from tradewinds.services.usage_service import daily_usage

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageEntry(BaseModel):
    role: str
    tier: str
    total_tokens: int
    calls: int


class DailyUsageResponse(BaseModel):
    date: date
    entries: list[UsageEntry]


@router.get("/daily", response_model=DailyUsageResponse)
async def get_daily_usage(
    day: date | None = Query(default=None, description="查询日期(UTC,默认今天)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DailyUsageResponse:
    """仅返回当前用户自己的用量,不暴露他人数据。"""
    if day is None:
        day = datetime.now(UTC).date()
    rows = await daily_usage(session, current_user.id, day=day)
    return DailyUsageResponse(
        date=day,
        entries=[
            UsageEntry(role=r.role, tier=r.tier, total_tokens=r.total_tokens, calls=r.calls)
            for r in rows
        ],
    )
