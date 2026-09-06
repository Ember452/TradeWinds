"""StructuredRunner 用量记录测试:成功调用记录一次,重试不重复计。"""

from typing import Any

from pydantic import BaseModel

from tradewinds.agents.orchestrator.llm import LLMResult, Message, ModelTier, Usage
from tradewinds.agents.orchestrator.structured import StructuredRunner


class Answer(BaseModel):
    number: int


class RecordingRecorder:
    def __init__(self) -> None:
        self.entries: list[tuple[int, str, str, int]] = []

    async def record(self, user_id: int, role: str, tier: ModelTier, usage: Usage) -> None:
        self.entries.append((user_id, role, tier.value, usage.total_tokens))


class FakeProvider:
    def __init__(self, contents: list[Any]) -> None:
        self._contents = list(contents)
        self.calls = 0

    async def complete(self, messages: list[Message], **kwargs: Any) -> LLMResult:
        self.calls += 1
        return LLMResult(
            content=self._contents.pop(0),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    def stream(self, messages: list[Message], **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


def _result_provider(content: Any) -> FakeProvider:
    return FakeProvider([content])


async def test_records_usage_once_on_success() -> None:
    recorder = RecordingRecorder()
    provider = _result_provider(Answer(number=1))
    runner = StructuredRunner(provider, recorder=recorder)

    await runner.run("p", Answer, model=ModelTier.low, role="analyst", user_id=7)

    assert recorder.entries == [(7, "analyst", "low", 15)]
    assert provider.calls == 1


async def test_no_recording_without_user_context() -> None:
    recorder = RecordingRecorder()
    runner = StructuredRunner(_result_provider(Answer(number=1)), recorder=recorder)

    await runner.run("p", Answer, model=ModelTier.low)

    assert recorder.entries == []


async def test_validation_retry_records_only_final_success() -> None:
    recorder = RecordingRecorder()
    provider = FakeProvider([{"bad": "output"}, Answer(number=2)])
    runner = StructuredRunner(provider, recorder=recorder)

    answer = await runner.run("p", Answer, model=ModelTier.low, role="editor", user_id=3)

    assert answer == Answer(number=2)
    assert provider.calls == 2
    # 只按最终成功调用记录一次
    assert recorder.entries == [(3, "editor", "low", 15)]
