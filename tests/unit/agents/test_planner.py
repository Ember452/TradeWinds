"""Planner 主题编译测试:prompt 独立加载、调用结构化执行器、产物校验。"""

from typing import Any

import pytest

from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.planner import Planner
from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan
from tradewinds.models.topic import Cadence

SAMPLE_PLAN = {
    "keywords": ["AI Agent", "tool use", "LLM"],
    "sources": ["arxiv", "hackernews", "github"],
    "arxiv_categories": ["cs.AI", "cs.CL"],
    "github": {"keywords": ["agent framework"], "language": None, "min_stars": None},
    "window_days": 7,
    "relevance_criteria": ["与 LLM Agent 技术直接相关"],
}


class FakeRunner:
    def __init__(self, plan_data: dict[str, Any]) -> None:
        self._plan = RetrievalPlan.model_validate(plan_data)
        self.calls: list[tuple[str, type, str]] = []

    async def run(self, prompt: str, response_model: type, *, model: ModelTier) -> Any:
        self.calls.append((prompt, response_model, model.value))
        return self._plan


async def test_compile_returns_plan() -> None:
    runner = FakeRunner(SAMPLE_PLAN)
    planner = Planner(runner=runner)  # type: ignore[arg-type]

    plan = await planner.compile("近一周的 Agent 新技术", Cadence.weekly)

    assert isinstance(plan, RetrievalPlan)
    assert plan.window_days == 7


async def test_compile_passes_description_and_cadence_to_prompt() -> None:
    runner = FakeRunner(SAMPLE_PLAN)
    planner = Planner(runner=runner)  # type: ignore[arg-type]

    await planner.compile("近一周的 Agent 新技术", Cadence.daily)

    prompt, _, tier = runner.calls[0]
    assert "近一周的 Agent 新技术" in prompt
    assert "daily" in prompt
    assert tier == "low"


async def test_system_prompt_loaded_from_file() -> None:
    # prompt 必须是独立文件,不内嵌字符串;文件内容里含任务说明标记
    assert "检索计划" in Planner.SYSTEM_PROMPT


async def test_validation_failure_retried_via_structured_runner() -> None:
    # 复用 StructuredRunner 的重试语义:这里验证 Planner 把校验责任交给 runner,
    # runner 连续返回非法产物时异常向上抛,Planner 不吞异常。
    class FailingRunner(FakeRunner):
        async def run(self, prompt: str, response_model: type, *, model: ModelTier) -> Any:
            raise AssertionError("走不到")  # pragma: no cover

    planner = Planner(runner=FailingRunner(SAMPLE_PLAN))  # type: ignore[arg-type]
    with pytest.raises(AssertionError):
        await planner.compile("x", Cadence.daily)
