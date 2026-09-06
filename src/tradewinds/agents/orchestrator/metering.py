"""LLM 计量:按用户/角色/档位记录 token 用量。

UsageRecorder 是编排层定义的落点协议;日志实现用于本地调试,
落库实现见 services/usage_service.py,接口一致,替换不影响调用方。
"""

from typing import Protocol

import structlog
from pydantic import BaseModel

from tradewinds.agents.orchestrator.llm import ModelTier, Usage

logger = structlog.get_logger(__name__)


class UsageRecorder(Protocol):
    async def record(self, user_id: int, role: str, tier: ModelTier, usage: Usage) -> None: ...


class MeteringContext(BaseModel):
    user_id: int
    role: str


class MeteringRecorder:
    """日志实现:结构化日志落点(llm_usage 事件)。"""

    async def record(self, user_id: int, role: str, tier: ModelTier, usage: Usage) -> None:
        logger.info(
            "llm_usage",
            user_id=user_id,
            role=role,
            tier=tier.value,
            usage=usage.model_dump(),
        )
