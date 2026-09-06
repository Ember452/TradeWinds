"""Analyst:对候选条目统一打分(0-10)与聚类,走低档位模型。"""

from pathlib import Path

from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.orchestrator.metering import UsageRecorder
from tradewinds.agents.orchestrator.structured import StructuredRunner
from tradewinds.agents.schemas.scored_item import AnalystOutput, ScoredItem
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.models.topic import Topic
from tradewinds.services.preference_service import build_scoring_prompt_section
from tradewinds.tools.base import CandidateItem

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "analyst.md"
_RAW_CONTENT_MAX = 1500
_UNMATCHED_KEY = "unmatched"


class Analyst:
    SYSTEM_PROMPT = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    def __init__(self, runner: StructuredRunner, *, recorder: UsageRecorder | None = None) -> None:
        self._runner = runner
        self._recorder = recorder

    async def score(
        self, items: list[CandidateItem], topic: Topic, *, preferences: list[str] | None = None
    ) -> list[ScoredItem]:
        """按主题相关性逐条评分;LLM 未覆盖的条目计 0 分进 unmatched 聚类。

        preferences 为跨会话偏好画像(点击历史/其他主题关键词),仅作参考信号。
        """
        if not items:
            return []

        prompt = self._build_prompt(items, topic, preferences or [])
        output = await self._runner.run(
            prompt, AnalystOutput, model=ModelTier.low, role="analyst", user_id=topic.user_id
        )

        by_url = {entry.url: entry for entry in output.items}
        scored: list[ScoredItem] = []
        for item in items:
            entry = by_url.get(item.url)
            if entry is None:
                scored.append(ScoredItem(item=item, score=0.0, cluster_key=_UNMATCHED_KEY))
            else:
                scored.append(
                    ScoredItem(item=item, score=entry.score, cluster_key=entry.cluster_key)
                )
        return scored

    def _build_prompt(
        self, items: list[CandidateItem], topic: Topic, preferences: list[str]
    ) -> str:
        criteria = _criteria_of(topic)
        lines = [
            self.SYSTEM_PROMPT,
            "---",
            f"主题名称:{topic.name}",
            f"主题描述:{topic.description}",
            "判定标准:",
        ]
        lines += [f"- {c}" for c in criteria]
        lines.append(build_scoring_prompt_section(preferences))
        lines.append("")
        lines.append("候选条目:")
        for item in items:
            content = truncate_text(normalize_whitespace(item.raw_content), _RAW_CONTENT_MAX)
            published = item.published_at.date().isoformat() if item.published_at else "未知"
            lines.append(
                f"- URL: {item.url}\n  标题: {item.title}\n  发布: {published}\n  内容: {content}"
            )
        return "\n".join(lines)


def _criteria_of(topic: Topic) -> list[str]:
    """判定标准来自 topic.plan(JSONB);缺失时退回主题描述。"""
    plan = topic.plan or {}
    criteria = plan.get("relevance_criteria")
    if isinstance(criteria, list) and criteria:
        return [str(c) for c in criteria]
    return [topic.description]
