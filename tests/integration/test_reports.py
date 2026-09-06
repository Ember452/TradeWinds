"""周期报告集成测试:管道 run → 报告 upsert 幂等、列表、分享与公开访问。

标记 integration:CI 起 PostgreSQL/Redis service 运行;管道组件以假件替换。
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.item_digest import ItemDigest
from tradewinds.agents.schemas.scored_item import AnalystOutput, ItemScore
from tradewinds.api.app import create_app
from tradewinds.tools.base import CandidateItem

pytestmark = pytest.mark.integration

MARKER = uuid.uuid4().hex[:8]


class FakePlanner:
    async def compile(self, description: str, cadence: Any) -> Any:
        from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan

        return RetrievalPlan.model_validate(
            {
                "keywords": ["agent", "quant"],
                "sources": ["arxiv"],
                "arxiv_categories": [],
                "github": None,
                "window_days": 7,
                "relevance_criteria": ["相关"],
            }
        )


class FakeSourceClient:
    name = "arxiv"

    async def search(
        self, plan: Any, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        return [
            CandidateItem(
                source="arxiv",
                url=f"https://example.com/{MARKER}-{i}",
                title=f"Paper {i}",
                raw_content="content",
                published_at=datetime.now(UTC),
            )
            for i in range(2)
        ]


class FakeRunner:
    async def run(self, prompt: str, response_model: Any, *, model: Any) -> Any:
        if response_model is AnalystOutput:
            return AnalystOutput(
                items=[
                    ItemScore(url=f"https://example.com/{MARKER}-{i}", score=8.0, cluster_key="k")
                    for i in range(2)
                ]
            )
        if response_model is ItemDigest:
            return ItemDigest(summary="s", reason="r")
        raise AssertionError(response_model)  # pragma: no cover


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        app = test_client.app
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([FakeSourceClient()])
        app.state.analyst = Analyst(runner=FakeRunner())  # type: ignore[arg-type]
        app.state.editor = Editor(runner=FakeRunner())  # type: ignore[arg-type]
        yield test_client


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"report-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_topic_and_run(client: TestClient, headers: dict[str, str]) -> int:
    topic_id = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "报告主题", "description": "d", "cadence": "weekly"},
    ).json()["topic"]["id"]
    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text
    return topic_id


def test_run_creates_and_updates_period_report(client: TestClient) -> None:
    headers = _auth_headers(client)
    topic_id = _create_topic_and_run(client, headers)

    reports = client.get(f"/api/v1/topics/{topic_id}/reports", headers=headers).json()
    assert len(reports) == 1
    report = reports[0]
    assert report["period_type"] == "weekly"
    assert report["item_count"] == 2
    assert f"https://example.com/{MARKER}-0" in report["content"]

    # 再 run 一次:同一周期只有一份报告,内容重算
    client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    reports = client.get(f"/api/v1/topics/{topic_id}/reports", headers=headers).json()
    assert len(reports) == 1
    assert reports[0]["item_count"] == 2


def test_share_flow_and_public_access(client: TestClient) -> None:
    headers = _auth_headers(client)
    topic_id = _create_topic_and_run(client, headers)
    report_id = client.get(f"/api/v1/topics/{topic_id}/reports", headers=headers).json()[0]["id"]

    shared = client.post(f"/api/v1/reports/{report_id}/share", headers=headers).json()
    assert shared["share_token"]

    # 再次分享复用同一 token
    again = client.post(f"/api/v1/reports/{report_id}/share", headers=headers).json()
    assert again["share_token"] == shared["share_token"]

    # 无鉴权公开访问
    public = client.get(shared["share_path"])
    assert public.status_code == 200
    assert public.json()["title"] == "报告主题"
    assert public.json()["item_count"] == 2

    # 错误 token → 404
    assert client.get("/api/v1/share/reports/no-such-token").status_code == 404

    # 未分享的报告不能经公开路径访问(share_token 为空,天然不可达)
    assert client.get(f"/api/v1/share/reports/{uuid.uuid4().hex}").status_code == 404
