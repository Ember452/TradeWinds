"""源客户端契约测试的公共工具:fixture 加载与 MockTransport 客户端。"""

import pathlib
from typing import Any

import httpx
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(*parts: str) -> str:
        return (FIXTURES_DIR.joinpath(*parts)).read_text(encoding="utf-8")

    return _load


@pytest.fixture
def mock_client():
    def _make(handler: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return _make
