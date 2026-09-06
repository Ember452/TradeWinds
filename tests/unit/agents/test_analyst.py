"""Analyst 评分聚类测试:0-10 分、聚类键、raw_content 截断。"""

from datetime import UTC, datetime

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.schemas.scored_item import AnalystOutput, ItemScore
from tradewinds.models.topic import Cadence, Topic
from tradewinds.tools.base import CandidateItem

TOPIC = Topic(
    id=1,
    user_id=1,
    name="AI Agent 动态",
    description="关注 LLM Agent 技术进展",
    cadence=Cadence.weekly,
    plan={
        "keywords": ["agent", "quant"],
        "relevance_criteria": ["与 Agent 直接相关", "排除营销稿"],
        "window_days": 7,
    },
)


def _item(url: str, content: str = "c") -> CandidateItem:
    return CandidateItem(
        source="arxiv",
        url=url,
        title=f"t-{url}",
        raw_content=content,
        published_at=datetime.now(UTC),
    )


class FakeRunner:
    def __init__(self, output: AnalystOutput) -> None:
        self._output = output
        self.prompts: list[str] = []

    async def run(
        self, prompt: str, response_model: type, *, model: ModelTier, **kwargs: object
    ) -> AnalystOutput:
        assert response_model is AnalystOutput
        self.prompts.append(prompt)
        return self._output


async def test_score_merges_llm_output_with_items() -> None:
    runner = FakeRunner(
        AnalystOutput(
            items=[
                ItemScore(url="https://a/1", score=8.5, cluster_key="tool-frameworks"),
                ItemScore(url="https://a/2", score=3.0, cluster_key="evals"),
            ]
        )
    )
    analyst = Analyst(runner=runner)  # type: ignore[arg-type]

    scored = await analyst.score([_item("https://a/1"), _item("https://a/2")], TOPIC)

    assert scored[0].score == 8.5
    assert scored[0].cluster_key == "tool-frameworks"
    assert scored[1].score == 3.0


async def test_item_missing_from_llm_output_defaults_to_zero() -> None:
    runner = FakeRunner(
        AnalystOutput(items=[ItemScore(url="https://a/1", score=7, cluster_key="x")])
    )
    analyst = Analyst(runner=runner)  # type: ignore[arg-type]

    scored = await analyst.score([_item("https://a/1"), _item("https://a/2")], TOPIC)

    unmatched = next(s for s in scored if s.item.url == "https://a/2")
    assert unmatched.score == 0.0
    assert unmatched.cluster_key == "unmatched"


async def test_raw_content_truncated_before_llm() -> None:
    long_content = "x" * 50_000
    runner = FakeRunner(AnalystOutput(items=[]))
    analyst = Analyst(runner=runner)  # type: ignore[arg-type]

    await analyst.score([_item("https://a/1", long_content)], TOPIC)

    assert len(runner.prompts[0]) < 20_000
    assert long_content not in runner.prompts[0]


async def test_prompt_contains_topic_and_criteria() -> None:
    runner = FakeRunner(AnalystOutput(items=[]))
    analyst = Analyst(runner=runner)  # type: ignore[arg-type]

    await analyst.score([_item("https://a/1")], TOPIC)

    assert "AI Agent 动态" in runner.prompts[0]
    assert "与 Agent 直接相关" in runner.prompts[0]
