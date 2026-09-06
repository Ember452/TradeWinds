"""即时推送集成测试:阈值触发、24h 聚类抑制、重复不重推。

标记 integration:CI 起 PostgreSQL/Redis service 运行;管道组件与
邮件渠道以假件替换(渠道未配置 → 投递记 skipped)。
"""

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.push_judge import ItemPushDecision
from tradewinds.agents.retriever import Retriever
from tradewinds.agents.schemas.item_digest import ItemDigest
from tradewinds.agents.schemas.scored_item import AnalystOutput, ItemScore
from tradewinds.api.app import create_app
from tradewinds.tasks.push_tasks import send_push
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
            for i in range(3)
        ]


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
            # item-0 与 item-1 同聚类且超阈值;item-2 低于即时阈值但仍 accepted
            return AnalystOutput(
                items=[
                    ItemScore(url=f"https://example.com/{MARKER}-0", score=9.0, cluster_key="hot"),
                    ItemScore(url=f"https://example.com/{MARKER}-1", score=8.5, cluster_key="hot"),
                    ItemScore(url=f"https://example.com/{MARKER}-2", score=6.5, cluster_key="warm"),
                ]
            )
        if response_model is ItemDigest:
            return ItemDigest(summary="s", reason="r")
        raise AssertionError(response_model)  # pragma: no cover


class FakePushJudge:
    """全推判定:行为与无 Judge 一致。"""

    def __init__(self) -> None:
        self.calls = 0

    async def decide(
        self, topic: Any, items: list[Any], *, preferences: list[str]
    ) -> dict[str, ItemPushDecision]:
        self.calls += 1
        return {i.url: ItemPushDecision(url=i.url, push=True, reason="判定通过") for i in items}


class SkippingPushJudge:
    """首条(url 以 -0 结尾)判 skip,其余照推。"""

    async def decide(
        self, topic: Any, items: list[Any], *, preferences: list[str]
    ) -> dict[str, ItemPushDecision]:
        return {
            i.url: ItemPushDecision(url=i.url, push=not i.url.endswith("-0"), reason="契合度不足")
            if i.url.endswith("-0")
            else ItemPushDecision(url=i.url, push=True, reason="判定通过")
            for i in items
        }


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as test_client:
        app = test_client.app
        # celery 的 send_task 不受 task_always_eager 影响,投递改为同步执行任务函数
        app.state.push_dispatch = lambda push_log_id: send_push.apply(args=[push_log_id])
        app.state.planner = FakePlanner()
        app.state.retriever = Retriever([FakeSourceClient()])
        app.state.analyst = Analyst(runner=FakeRunner())  # type: ignore[arg-type]
        app.state.editor = Editor(runner=FakeRunner())  # type: ignore[arg-type]
        app.state.push_judge = FakePushJudge()
        yield test_client


async def _seed_score_history(topic_id: int, score: float, count: int, marker: str) -> None:
    """直插 accepted 历史评分,构造"高分主题"画像。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            for i in range(count):
                await conn.execute(
                    text(
                        "INSERT INTO items (topic_id, source, url, url_hash, title, raw_content,"
                        " score, cluster_key, status)"
                        " VALUES (:t, 'arxiv', :url, :hash, 'h', 'c', :score, 'hot', 'accepted')"
                    ),
                    {
                        "t": topic_id,
                        "url": f"https://history.example/{marker}-{i}",
                        "hash": f"{marker}-hist-{i}",
                        "score": score,
                    },
                )
    finally:
        await engine.dispose()


def _auth_headers(client: TestClient) -> dict[str, str]:
    email = f"imm-{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-password"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret-password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _push_logs(topic_id: int) -> list[dict[str, Any]]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT push_type, cluster_key, digest_key, status "
                    "FROM push_log WHERE topic_id = :t ORDER BY id"
                ),
                {"t": topic_id},
            )
            return [dict(r._mapping) for r in rows]
    finally:
        await engine.dispose()


def test_immediate_push_threshold_and_cluster_suppression(client: TestClient) -> None:
    import asyncio

    headers = _auth_headers(client)
    topic_id = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "即时推送主题", "description": "d", "cadence": "daily"},
    ).json()["topic"]["id"]

    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text

    logs = asyncio.run(_push_logs(topic_id))
    digests = [log for log in logs if log["push_type"] == "digest"]
    immediates = [log for log in logs if log["push_type"] == "immediate"]

    # 汇总邮件 1 条(3 条 accepted)
    assert len(digests) == 1
    # 即时推送:item-0(9.0)入选;item-1(8.5)同聚类 24h 内被抑制;
    # item-2(6.5)低于阈值不触发
    assert len(immediates) == 1
    assert immediates[0]["cluster_key"] == "hot"
    # 渠道未配置 → 投递记 skipped
    assert immediates[0]["status"] == "skipped"

    # 再跑一次:所有推送幂等,不产生新记录
    client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    logs_again = asyncio.run(_push_logs(topic_id))
    assert len(logs_again) == len(logs)


def test_adaptive_threshold_suppresses_on_high_history(client: TestClient) -> None:
    import asyncio

    headers = _auth_headers(client)
    topic_id = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "高分主题", "description": "d", "cadence": "daily"},
    ).json()["topic"]["id"]

    # 冷启动基线:无历史时 8.5 分条目(阈值 8.0)会触发即时推送
    asyncio.run(_seed_score_history(topic_id, 9.0, 12, uuid.uuid4().hex[:6]))
    # 12 条 9.0 分历史 → 中位数 9.0 → 有效阈值抬到 9.0
    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text

    import asyncio as _aio

    from sqlalchemy import text as _text
    from sqlalchemy.ext.asyncio import create_async_engine as _cae

    async def _immediates() -> list[dict[str, Any]]:
        engine = _cae(os.environ["TRADEWINDS_DATABASE_URL"])
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    _text(
                        "SELECT digest_key FROM push_log WHERE topic_id = :t"
                        " AND push_type = 'immediate'"
                    ),
                    {"t": topic_id},
                )
                return [dict(r._mapping) for r in rows]
        finally:
            await engine.dispose()

    immediates = _aio.run(_immediates())
    # 本文件 FakeRunner 给 item-0 9.0 / item-1 8.5:自适应阈值抬到 9.0 后
    # 只有 9.0 触发,8.5 被抑制(全局阈值 8.0 会放行两条)→ 恰好 1 条
    assert len(immediates) == 1


def test_push_judge_skip_leaves_audited_log(client: TestClient) -> None:
    """Judge 判 skip 的条目:建 skipped 记录留痕、不入队;照推的记录判定理由。"""
    import asyncio

    client.app.state.push_judge = SkippingPushJudge()
    headers = _auth_headers(client)
    topic_id = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"name": "Judge 守门主题", "description": "d", "cadence": "daily"},
    ).json()["topic"]["id"]

    run = client.post(f"/api/v1/topics/{topic_id}/run", headers=headers)
    assert run.status_code == 200, run.text

    async def _immediate_logs() -> list[dict[str, Any]]:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(os.environ["TRADEWINDS_DATABASE_URL"])
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text(
                        "SELECT pl.status, pl.judge_reason, pl.error, i.url AS url"
                        " FROM push_log pl JOIN items i ON i.id = (pl.item_ids->>0)::int"
                        " WHERE pl.topic_id = :t AND pl.push_type = 'immediate'"
                    ),
                    {"t": topic_id},
                )
                return [dict(r._mapping) for r in rows]
        finally:
            await engine.dispose()

    logs = {row["url"]: row for row in asyncio.run(_immediate_logs())}

    # 判 skip:url=-0 建 skipped 记录 + 理由,不投递(error 为空)
    skipped = logs[f"https://example.com/{MARKER}-0"]
    assert skipped["status"] == "skipped"
    assert skipped["judge_reason"] == "契合度不足"
    assert skipped["error"] is None
    # 照推:url=-1 进投递(渠道未配置 → skipped),判定理由留痕
    pushed = logs[f"https://example.com/{MARKER}-1"]
    assert pushed["status"] == "skipped"
    assert pushed["judge_reason"] == "判定通过"
    assert pushed["error"] == "email_disabled"
