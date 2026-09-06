"""PushJudge 单测:批量判定解析、prompt 组装、计量角色透传。"""

from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.push_judge import ItemPushDecision, PushJudge, PushJudgement
from tradewinds.models.item import Item
from tradewinds.models.topic import Topic


class FakeRunner:
    def __init__(self, judgement: PushJudgement) -> None:
        self._judgement = judgement
        self.calls: list[tuple[str, type, ModelTier, str | None, int | None]] = []

    async def run(
        self,
        prompt: str,
        response_model: type,
        *,
        model: ModelTier,
        role: str | None = None,
        user_id: int | None = None,
    ) -> PushJudgement:
        self.calls.append((prompt, response_model, model, role, user_id))
        return self._judgement


def _topic() -> Topic:
    topic = Topic(name="Agent 动态", description="近一周 Agent 新技术", user_id=1)
    topic.plan = {
        "keywords": ["agent"],
        "sources": ["arxiv"],
        "relevance_criteria": ["与 Agent 框架直接相关", "有代码或论文产出"],
    }
    return topic


def _item(**overrides: object) -> Item:
    fields: dict[str, object] = {
        "id": 1,
        "url": "https://example.com/a",
        "title": "重大发布",
        "score": 8.8,
        "summary": "某框架发布 2.0",
        "reason": "影响面广",
    }
    fields.update(overrides)
    return Item(**fields)  # type: ignore[arg-type]


async def test_decide_returns_judgements_keyed_by_url() -> None:
    judgement = PushJudgement(
        decisions=[
            ItemPushDecision(url="https://example.com/a", push=True, reason="重大发布值得推"),
            ItemPushDecision(url="https://example.com/b", push=False, reason="例行更新"),
        ]
    )
    runner = FakeRunner(judgement)
    judge = PushJudge(runner)

    items = [_item(), _item(id=2, url="https://example.com/b")]
    result = await judge.decide(_topic(), items, preferences=[])

    assert result["https://example.com/a"].push is True
    assert result["https://example.com/b"].push is False
    assert result["https://example.com/b"].reason == "例行更新"


async def test_prompt_carries_topic_criteria_and_items() -> None:
    runner = FakeRunner(PushJudgement())
    judge = PushJudge(runner)

    await judge.decide(_topic(), [_item()], preferences=["关注 RAG"])

    prompt = runner.calls[0][0]
    assert "Agent 动态" in prompt
    assert "与 Agent 框架直接相关" in prompt
    assert "https://example.com/a" in prompt
    assert "某框架发布 2.0" in prompt
    assert "关注 RAG" in prompt


async def test_decide_uses_low_tier_and_push_judge_role() -> None:
    runner = FakeRunner(PushJudgement())
    judge = PushJudge(runner)

    await judge.decide(_topic(), [_item()], preferences=[])

    _, response_model, model, role, user_id = runner.calls[0]
    assert response_model is PushJudgement
    assert model is ModelTier.low
    assert role == "push_judge"
    assert user_id == 1
