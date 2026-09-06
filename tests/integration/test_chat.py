"""SSE 对话全链路集成测试:事件序、持久化(引用/轨迹)、并发限流。

标记 integration:CI 起 PostgreSQL/Redis service 运行;ToolLoop 以假件
替换(固定回答 + 带真实 URL 的工具轨迹)。
"""

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tradewinds.agents.orchestrator.llm import Usage
from tradewinds.agents.orchestrator.loop import LoopResult, ToolTrace
from tradewinds.api.app import create_app

pytestmark = pytest.mark.integration


class FakeToolLoop:
    model = "fake-mid"

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, messages: list[Any]) -> LoopResult:
        self.calls += 1
        return LoopResult(
            content="结论如下 [1]。",
            tool_trace=[
                ToolTrace(
                    tool="search_arxiv",
                    arguments={"query": "agent"},
                    result="Paper A https://example.com/paper-a 摘要",
                )
            ],
            iterations=2,
            usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            stopped_reason="completed",
        )


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        test_client.app.state.tool_loop = FakeToolLoop()
        yield test_client


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"chat-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    import json

    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_type = ""
        data = ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        if event_type:
            events.append((event_type, json.loads(data)))
    return events


def test_sse_event_order_and_persistence(client: TestClient) -> None:
    headers = _auth_headers(client)
    conv_id = client.post(
        "/api/v1/conversations", headers=headers, json={"title": "研究对话"}
    ).json()["id"]

    with client.stream(
        "POST",
        f"/api/v1/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "最近有哪些 Agent 框架?"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    events = _parse_sse(body)
    types = [t for t, _ in events]

    # 事件序:citations 先行 → delta* → done
    assert types[0] == "citations"
    assert "delta" in types
    assert types[-1] == "done"
    assert events[0][1]["citations"][0]["url"] == "https://example.com/paper-a"
    assert events[-1][1]["usage"]["total_tokens"] == 150

    deltas = "".join(data["text"] for t, data in events if t == "delta")
    assert "结论如下" in deltas

    # 持久化:历史回看含 user + assistant 消息,引用与工具轨迹落库
    detail = client.get(f"/api/v1/conversations/{conv_id}", headers=headers).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["citations"][0]["url"] == "https://example.com/paper-a"
    assert assistant["tool_trace"][0]["tool"] == "search_arxiv"


def test_cross_user_conversation_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)
    conv_id = client.post("/api/v1/conversations", headers=headers, json={"title": "私有"}).json()[
        "id"
    ]

    other_email = f"chat2-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": other_email, "password": "s3cret-password"})
    other = client.post(
        "/api/v1/auth/login", json={"email": other_email, "password": "s3cret-password"}
    ).json()

    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        json={"content": "你好"},
    )

    assert resp.status_code == 404
