"""FastAPI 应用工厂:所有路由经 create_app() 挂载。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.orchestrator.llm import ModelTier, OpenAICompatibleProvider
from tradewinds.agents.orchestrator.structured import StructuredRunner
from tradewinds.agents.planner import Planner
from tradewinds.agents.retriever import Retriever
from tradewinds.api.errors import register_exception_handlers
from tradewinds.api.health import router as health_router
from tradewinds.api.v1 import api_v1_router
from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.core.logging import setup_logging
from tradewinds.core.redis_client import create_redis_client
from tradewinds.tools.arxiv import ArxivClient
from tradewinds.tools.base import RateLimiter
from tradewinds.tools.github import GithubClient
from tradewinds.tools.hackernews import HackerNewsClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    app.state.session_factory = create_session_factory(engine)
    redis = create_redis_client(settings.redis_url)
    app.state.redis = redis

    # 编排层与信息源客户端:请求间隔 1s,对三个源并行留出并发额度
    http_client = httpx.AsyncClient(timeout=30, follow_redirects=True)
    limiter = RateLimiter(max_concurrency=5, min_interval_seconds=1.0)
    provider = OpenAICompatibleProvider(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model_map={
            ModelTier.low: settings.model_low,
            ModelTier.mid: settings.model_mid,
        },
    )
    runner = StructuredRunner(provider)
    app.state.planner = Planner(runner)
    app.state.analyst = Analyst(runner)
    app.state.editor = Editor(runner)
    app.state.retriever = Retriever(
        [
            ArxivClient(limiter, http_client),
            HackerNewsClient(limiter, http_client),
            GithubClient(limiter, http_client, token=settings.github_token),
        ]
    )
    app.state.http_client = http_client

    yield

    await http_client.aclose()
    await redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="TradeWinds", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_v1_router)
    return app
