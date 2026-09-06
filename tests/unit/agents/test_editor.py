"""Editor 单条摘要测试:走中档位模型、prompt 含主题与条目信息。"""

from datetime import UTC, datetime
from typing import Any

from tradewinds.agents.editor import Editor
from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.schemas.item_digest import ItemDigest
from tradewinds.models.topic import Cadence, Topic
from tradewinds.tools.base import CandidateItem

TOPIC = Topic(
    id=1, user_id=1, name="AI Agent 动态", description="LLM Agent 技术", cadence=Cadence.weekly
)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, type, str]] = []

    async def run(self, prompt: str, response_model: type, *, model: ModelTier) -> Any:
        self.calls.append((prompt, response_model, model.value))
        return ItemDigest(summary="新框架发布,支持多工具编排", reason="直接对应主题关注点")


async def test_summarize_returns_digest() -> None:
    editor = Editor(runner=FakeRunner())  # type: ignore[arg-type]
    item = CandidateItem(
        source="arxiv",
        url="https://arxiv.org/abs/1",
        title="New Agent Framework",
        raw_content="content",
        published_at=datetime(2026, 9, 5, tzinfo=UTC),
    )

    digest = await editor.summarize(item, TOPIC)

    assert digest.summary
    assert digest.reason


async def test_uses_mid_tier_and_includes_context() -> None:
    runner = FakeRunner()
    editor = Editor(runner=runner)  # type: ignore[arg-type]
    item = CandidateItem(
        source="arxiv", url="https://arxiv.org/abs/1", title="Title", raw_content="body"
    )

    await editor.summarize(item, TOPIC)

    prompt, response_model, tier = runner.calls[0]
    assert tier == "mid"
    assert response_model is ItemDigest
    assert "AI Agent 动态" in prompt
    assert "Title" in prompt
