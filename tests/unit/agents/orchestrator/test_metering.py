"""MeteringRecorder 测试:LLM 用量以结构化日志落点,Phase 3 起落库。"""

from structlog.testing import capture_logs

from tradewinds.agents.orchestrator.llm import ModelTier, Usage
from tradewinds.agents.orchestrator.metering import MeteringRecorder


async def test_record_logs_usage_fields() -> None:
    recorder = MeteringRecorder()

    with capture_logs() as logs:
        await recorder.record(
            user_id=1,
            role="planner",
            tier=ModelTier.low,
            usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

    assert len(logs) == 1
    entry = logs[0]
    assert entry["event"] == "llm_usage"
    assert entry["user_id"] == 1
    assert entry["role"] == "planner"
    assert entry["tier"] == "low"
    assert entry["usage"] == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
