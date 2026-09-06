"""Planner:把主题自然语言描述编译为结构化检索计划(RetrievalPlan)。"""

from pathlib import Path

from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.orchestrator.structured import StructuredRunner
from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.models.topic import Cadence

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "planner.md"


class Planner:
    """低档位模型即可胜任的主题编译角色,复用 StructuredRunner 的校验重试。"""

    SYSTEM_PROMPT = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    def __init__(self, runner: StructuredRunner) -> None:
        self._runner = runner

    async def compile(self, description: str, cadence: Cadence) -> RetrievalPlan:
        prompt = (
            f"{self.SYSTEM_PROMPT}\n\n---\n\n主题描述:{description}\n执行频率:{cadence.value}\n"
        )
        return await self._runner.run(prompt, RetrievalPlan, model=ModelTier.low)
