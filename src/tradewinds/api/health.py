"""健康检查端点。

/healthz 只探进程存活;/readyz 探外部依赖(DB/Redis)连通,语义分离。
"""

from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/healthz")
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


async def _check_db(session_factory: Any) -> Literal["ok", "fail"]:
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return "fail"
    return "ok"


async def _check_redis(redis: Any) -> Literal["ok", "fail"]:
    try:
        await redis.ping()
    except Exception:  # redis 客户端异常类型随版本变化,探活失败一律报 fail
        return "fail"
    return "ok"


async def _queue_backlog(redis: Any) -> int:
    """三个 Celery 队列的在途任务总数;读取失败返回 -1(不阻断就绪判定)。"""
    total = 0
    for queue in ("default", "pipeline", "push"):
        try:
            total += int(await redis.llen(queue))
        except Exception:
            return -1
    return total


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    checks = {
        "db": await _check_db(request.app.state.session_factory),
        "redis": await _check_redis(request.app.state.redis),
    }
    ready = all(status == "ok" for status in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "unavailable",
            "checks": checks,
            "queue_backlog": await _queue_backlog(request.app.state.redis),
        },
    )
