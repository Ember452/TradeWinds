"""推送闭环集成测试:管道跑完 → push_log 落库 → 任务投递(eager)→ 状态回写。

标记 integration:CI 起 PostgreSQL/Redis service 运行;邮件渠道未配置,
投递结果为 skipped(email_disabled),不访问真实 SMTP。
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
from tradewinds.tasks.push_tasks import send_push
from tradewinds.tools.base import CandidateItem, is_seen

pytestmark = pytest.mark.integration


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

    def __init__(self, marker: str) -> None:
        self._marker = marker

    async def search(
        self, plan: Any, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]:
        candidates = [
            CandidateItem(
                source="arxiv",
                url=f"https://example.com/{self._marker}-a",
                title="Paper A",
                raw_content="content",
                published_at=datetime.now(UTC),
            )
        ]
        return [c for c in candidates if not is_seen(c.url, topic_id, seen_hashes)]


class FakeRunner:
    async def run(
        self,
        prompt: str,
        response_model: Any,
        *,
        model: Any,
        role: str | None = None,
        user_id: int | None = None,
    ) -> Any:
        if response_model is AnalystOutput:
            return AnalystOutput(
                items=[ItemScore(url="https://example.com/placeholder", score=9.0, cluster_key="k")]
            )
        if response_model is ItemDigest:
            return ItemDigest(summary="s", reason="r")
        raise AssertionError(response_model)  # pragma: no cover


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        marker = uuid.uuid4().hex[:8]
        # celery 的 send_task 不受 task_always_eager 影响,投递改为同步执行任务函数
        test_client.app.state.push_dispatch = lambda push_log_id: send_push.apply(
            args=[push_log_id]
        )

        class PinnedSource(FakeSourceClient):
            async def search(
                self, plan: Any, *, topic_id: int, seen_hashes: set[str]
            ) -> list[CandidateItem]:
                return await FakeSourceClient(marker).search(
                    plan, topic_id=topic_id, seen_hashes=seen_hashes
                )

        class PinnedRunner(FakeRunner):
            async def run(
                self,
                prompt: str,
                response_model: Any,
                *,
                model: Any,
                role: str | None = None,
                user_id: int | None = None,
            ) -> Any:
                if response_model is AnalystOutput:
                    return AnalystOutput(
                        items=[
                            ItemScore(
                                url=f"https://example.com/{marker}-a", score=9.0, cluster_key="k"
                            )
                        ]
                    )
                return await FakeRunner().run(prompt, response_model, model=model)

        app = test_client.app
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([PinnedSource(marker)])
        app.state.analyst = Analyst(runner=PinnedRunner())  # type: ignore[arg-type]
        app.state.editor = Editor(runner=PinnedRunner())  # type: ignore[arg-type]
        yield test_client


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"push-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_pipeline_run_creates_push_log_and_marks_status(
    client: TestClient,
) -> None:
    headers = _auth_headers(client)
    created = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "推送主题", "description": "d", "cadence": "weekly"},
    ).json()
    topic_id = created["topic"]["id"]

    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text
    assert run.json()["accepted"] == 1

    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _query() -> list[dict[str, Any]]:
        engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text(
                        "SELECT status, error, recipient, push_type FROM push_log"
                        " WHERE topic_id = :t"
                    ),
                    {"t": topic_id},
                )
                return [dict(r._mapping) for r in rows]
        finally:
            await engine.dispose()

    logs = asyncio.run(_query())
    # 一次 run 产生三类推送:汇总邮件 + 高分即时 + 周期报告
    digests = [log for log in logs if log["push_type"] == "digest"]
    assert len(digests) == 1
    # SMTP 未配置 → 任务投递后标记 skipped,而非 pending 悬挂
    assert digests[0]["status"] == "skipped"
    assert digests[0]["recipient"].endswith("@example.com")
    assert all(log["status"] == "skipped" for log in logs)


def test_same_content_not_pushed_twice(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "去重主题", "description": "d", "cadence": "daily"},
    ).json()
    topic_id = created["topic"]["id"]

    client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)

    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _count() -> int:
        engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM push_log WHERE topic_id = :t AND push_type = 'digest'"
                    ),
                    {"t": topic_id},
                )
                return int(rows.scalar_one())
        finally:
            await engine.dispose()

    assert asyncio.run(_count()) == 1


def test_mute_endpoint_pauses_topic(client: TestClient) -> None:
    headers = _auth_headers(client)
    created = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "退订主题", "description": "d", "cadence": "daily"},
    ).json()
    topic_id = created["topic"]["id"]

    resp = client.post(f"/api/v1/topics/{topic_id}/mute", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "muted"
