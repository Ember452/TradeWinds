"""LLM 计量:按用户/角色/档位记录 token 用量。

Phase 2 先落结构化日志,Phase 3(Task 3.4)起落库做日聚合与配额扣减;
接口保持不变,替换实现不影响调用方。
"""

import structlog
from pydantic import BaseModel

from tradewinds.agents.orchestrator.llm import ModelTier, Usage

logger = structlog.get_logger(__name__)


class MeteringContext(BaseModel):
    user_id: int
    role: str


class MeteringRecorder:
    async def record(self, user_id: int, role: str, tier: ModelTier, usage: Usage) -> None:
        logger.info(
            "llm_usage",
            user_id=user_id,
            role=role,
            tier=tier.value,
            usage=usage.model_dump(),
        )
