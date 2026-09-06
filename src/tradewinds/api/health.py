"""健康检查端点:/healthz 只探进程存活,不检查外部依赖(/readyz 语义见后续任务)。"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/healthz")
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")
