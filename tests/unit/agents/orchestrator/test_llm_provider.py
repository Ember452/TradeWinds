"""OpenAI-compatible LLMProvider 测试:全部 mock SDK,不依赖外网。"""

from typing import Any

import httpx
import openai
import pytest
from pydantic import BaseModel

from tradewinds.agents.orchestrator.llm import (
    LLMResult,
    Message,
    ModelTier,
    OpenAICompatibleProvider,
)
from tradewinds.core.exceptions import LLMError

MODEL_MAP = {ModelTier.low: "test-low", ModelTier.mid: "test-mid"}


def _rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://llm.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


class _ConnectionError5xx(openai.APIConnectionError):
    """无 response 的连接类错误,Provider 也应重试。"""


class FakeCompletions:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeBetaCompletions:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _provider(
    completions: FakeCompletions, beta: FakeBetaCompletions | None = None
) -> OpenAICompatibleProvider:
    client = type("FakeClient", (), {})()
    client.chat = type("FakeChat", (), {})()
    client.chat.completions = completions
    if beta is not None:
        client.beta = type("FakeBeta", (), {})()
        client.beta.chat = type("FakeBetaChat", (), {})()
        client.beta.chat.completions = beta
    return OpenAICompatibleProvider(
        base_url="https://llm.test/v1", api_key="k", model_map=MODEL_MAP, client=client
    )


def _raw_completion(content: str, prompt: int = 10, completion: int = 5) -> Any:
    return type(
        "Completion",
        (),
        {
            "choices": [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()],
            "usage": type(
                "Usage", (), {"prompt_tokens": prompt, "completion_tokens": completion}
            )(),
        },
    )()


async def test_complete_returns_content_and_usage(monkeypatch) -> None:
    monkeypatch.setattr("tradewinds.agents.orchestrator.llm.asyncio.sleep", None)
    completions = FakeCompletions([_raw_completion("hello world")])
    provider = _provider(completions)

    result = await provider.complete([Message(role="user", content="hi")], model=ModelTier.low)

    assert isinstance(result, LLMResult)
    assert result.content == "hello world"
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert completions.calls[0]["model"] == "test-low"


async def test_structured_output_returns_validated_model(monkeypatch) -> None:
    class Score(BaseModel):
        value: int

    monkeypatch.setattr("tradewinds.agents.orchestrator.llm.asyncio.sleep", None)
    # openai 3.x 返回形状:解析结果在 choices[0].message.parsed
    message = type(
        "Message",
        (),
        {"parsed": Score(value=8), "content": None},
    )()
    parsed = type(
        "Parsed",
        (),
        {
            "choices": [type("Choice", (), {"message": message})()],
            "usage": type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})(),
        },
    )()
    beta = FakeBetaCompletions([parsed])
    provider = _provider(FakeCompletions([]), beta)

    result = await provider.complete(
        [Message(role="user", content="score it")], model=ModelTier.low, response_model=Score
    )

    assert result.content == Score(value=8)
    assert beta.calls[0]["response_format"] is Score


async def test_retry_on_429_then_succeeds(monkeypatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("tradewinds.agents.orchestrator.llm.asyncio.sleep", fake_sleep)
    completions = FakeCompletions([_rate_limit_error(), _rate_limit_error(), _raw_completion("ok")])
    provider = _provider(completions)

    result = await provider.complete([Message(role="user", content="hi")], model=ModelTier.low)

    assert result.content == "ok"
    assert len(completions.calls) == 3
    # 指数退避:1s、2s
    assert sleeps == [1.0, 2.0]


async def test_retry_exhausted_raises_llm_error(monkeypatch) -> None:
    async def fake_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr("tradewinds.agents.orchestrator.llm.asyncio.sleep", fake_sleep)
    completions = FakeCompletions([_rate_limit_error() for _ in range(4)])
    provider = _provider(completions)

    with pytest.raises(LLMError):
        await provider.complete([Message(role="user", content="hi")], model=ModelTier.low)

    # 首次调用 + 3 次重试
    assert len(completions.calls) == 4


async def test_non_retryable_error_raises_immediately(monkeypatch) -> None:
    request = httpx.Request("POST", "https://llm.test/v1/chat/completions")
    response = httpx.Response(400, request=request)
    completions = FakeCompletions([openai.BadRequestError("bad", response=response, body=None)])
    provider = _provider(completions)

    with pytest.raises(LLMError):
        await provider.complete([Message(role="user", content="hi")], model=ModelTier.low)

    assert len(completions.calls) == 1


async def test_stream_yields_deltas(monkeypatch) -> None:
    monkeypatch.setattr("tradewinds.agents.orchestrator.llm.asyncio.sleep", None)
    deltas = [
        type(
            "Chunk",
            (),
            {"choices": [type("C", (), {"delta": type("D", (), {"content": "he"})()})()]},
        )(),
        type(
            "Chunk",
            (),
            {"choices": [type("C", (), {"delta": type("D", (), {"content": "llo"})()})()]},
        )(),
    ]

    async def _gen() -> Any:
        for chunk in deltas:
            yield chunk

    completions = FakeCompletions([_gen()])
    provider = _provider(completions)

    chunks = [
        chunk
        async for chunk in provider.stream(
            [Message(role="user", content="hi")], model=ModelTier.mid
        )
    ]

    assert chunks == ["he", "llo"]
    assert completions.calls[0]["model"] == "test-mid"
    assert completions.calls[0]["stream"] is True
