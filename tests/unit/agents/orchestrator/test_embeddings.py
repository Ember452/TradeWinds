"""嵌入客户端单元测试:全部 mock SDK,不依赖外网。"""

from typing import Any

import httpx
import openai
import pytest

from tradewinds.agents.orchestrator.embeddings import OpenAICompatibleEmbedder
from tradewinds.core.exceptions import LLMError


def _embedder(results: list[Any]) -> OpenAICompatibleEmbedder:
    client = type("FakeClient", (), {})()
    client.embeddings = type("FakeEmbeddings", (), {})()
    client.embeddings.create = _make_create(results)
    return OpenAICompatibleEmbedder(
        base_url="https://llm.test/v1", api_key="k", model="test-embedding", client=client
    )


def _make_create(results: list[Any]):
    async def create(**kwargs: Any) -> Any:
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    return create


def _response(vector: list[float]) -> Any:
    data = type("Data", (), {"embedding": vector})()
    return type("Response", (), {"data": [data]})()


async def test_embed_returns_floats() -> None:
    embedder = _embedder([_response([1.0, 2.0, 3.0])])

    vector = await embedder.embed("hello")

    assert vector == [1.0, 2.0, 3.0]


async def test_api_error_wrapped_as_llm_error() -> None:
    request = httpx.Request("POST", "https://llm.test/v1/embeddings")
    response = httpx.Response(500, request=request)
    embedder = _embedder([openai.InternalServerError("boom", response=response, body=None)])

    with pytest.raises(LLMError):
        await embedder.embed("hello")


async def test_model_name_exposed() -> None:
    assert _embedder([]).model == "test-embedding"
