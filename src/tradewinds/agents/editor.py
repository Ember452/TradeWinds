"""Editor:为通过评分的条目生成单条摘要与推荐理由,走中档位模型。"""

from pathlib import Path

from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.orchestrator.metering import UsageRecorder
from tradewinds.agents.orchestrator.structured import StructuredRunner
from tradewinds.agents.schemas.item_digest import ItemDigest
from tradewinds.core.text import normalize_whitespace, truncate_text
from tradewinds.models.topic import Topic
from tradewinds.tools.base import CandidateItem

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "editor.md"
_RAW_CONTENT_MAX = 2000


class Editor:
    SYSTEM_PROMPT = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    def __init__(self, runner: StructuredRunner, *, recorder: UsageRecorder | None = None) -> None:
        self._runner = runner
        self._recorder = recorder

    async def summarize(self, item: CandidateItem, topic: Topic) -> ItemDigest:
        prompt = (
            f"{self.SYSTEM_PROMPT}\n---\n"
            f"订阅主题:{topic.name} —— {topic.description}\n"
            f"条目标题:{item.title}\n"
            f"来源:{item.source}\n"
            f"发布时间:{item.published_at.date().isoformat() if item.published_at else '未知'}\n"
            f"原文内容:{truncate_text(normalize_whitespace(item.raw_content), _RAW_CONTENT_MAX)}\n"
        )
        return await self._runner.run(
            prompt, ItemDigest, model=ModelTier.mid, role="editor", user_id=topic.user_id
        )
