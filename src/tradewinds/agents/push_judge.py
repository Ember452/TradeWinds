"""Push Judge:即时推送前的低档 LLM 守门,逐条判定是否值得打断用户。

判定发生在阈值过滤之后、PushLog 创建之前;调用失败由调用方失败开放
(fail-open),LLM 故障不改变既有推送行为(docs/plans/2026-09-06-agent-
experience-upgrade.md Task D)。
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.orchestrator.metering import UsageRecorder
from tradewinds.agents.orchestrator.structured import StructuredRunner
from tradewinds.core.text import truncate_text
from tradewinds.models.item import Item
from tradewinds.models.topic import Topic

_PROMPT_PATH = Path(__file__).parent / "prompts" / "push_judge.md"
_SUMMARY_MAX = 500


class ItemPushDecision(BaseModel):
    """单条候选的判定:url 为主键,push=是否即时推送,reason=判定依据。"""

    url: str
    push: bool
    reason: str


class PushJudgement(BaseModel):
    """一次批量判定的产物,与候选条目一一对应。"""

    decisions: list[ItemPushDecision] = []


class PushJudge:
    SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

    def __init__(self, runner: StructuredRunner, *, recorder: UsageRecorder | None = None) -> None:
        self._runner = runner
        self._recorder = recorder

    async def decide(
        self, topic: Topic, items: list[Item], *, preferences: list[str]
    ) -> dict[str, ItemPushDecision]:
        """批量判定候选条目;返回以 url 为键的判定表。"""
        plan: dict[str, Any] = dict(topic.plan or {})
        criteria_raw = plan.get("relevance_criteria", [])
        criteria_items = [str(c) for c in criteria_raw] if isinstance(criteria_raw, list) else []
        criteria = "\n".join(f"- {c}" for c in criteria_items)
        preference_text = "\n".join(f"- {p}" for p in preferences) if preferences else "无"
        lines = [
            f"- url:{item.url}\n"
            f"  标题:{item.title}\n"
            f"  评分:{item.score}\n"
            f"  摘要:{truncate_text(item.summary or '', _SUMMARY_MAX)}\n"
            f"  推荐理由:{item.reason or ''}"
            for item in items
        ]
        prompt = (
            f"{self.SYSTEM_PROMPT}\n---\n"
            f"订阅主题:{topic.name} —— {topic.description}\n"
            f"相关性判定标准:\n{criteria}\n"
            f"用户历史偏好:\n{preference_text}\n"
            "候选条目:\n" + "\n".join(lines)
        )
        judgement = await self._runner.run(
            prompt,
            PushJudgement,
            model=ModelTier.low,
            role="push_judge",
            user_id=topic.user_id,
        )
        return {decision.url: decision for decision in judgement.decisions}
