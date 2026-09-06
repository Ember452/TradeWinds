"""FastAPI 应用工厂:所有路由经 create_app() 挂载。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from tradewinds.agents.chat_tools import build_chat_registry
from tradewinds.agents.orchestrator.llm import ModelTier
from tradewinds.agents.orchestrator.loop import ToolLoop
from tradewinds.agents.runtime import build_pipeline_components
from tradewinds.api.errors import register_exception_handlers
from tradewinds.api.health import router as health_router
from tradewinds.api.v1 import api_v1_router
from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.core.logging import setup_logging
from tradewinds.core.redis_client import create_redis_client
from tradewinds.push.email_channel import EmailChannel, EmailChannelConfig
from tradewinds.services.chat_service import UserConcurrencyLimiter
from tradewinds.services.usage_service import SessionUsageRecorder
from tradewinds.tasks.celery_app import PUSH_TASK, celery_app, configure_broker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    app.state.session_factory = create_session_factory(engine)
    redis = create_redis_client(settings.redis_url)
    app.state.redis = redis

    # API 进程内手动触发 run 也会入队推送任务,故同样注入 broker 配置
    configure_broker(celery_app, settings)

    components = build_pipeline_components(
        settings, usage_recorder=SessionUsageRecorder(app.state.session_factory)
    )
    app.state.planner = components.planner
    app.state.analyst = components.analyst
    app.state.editor = components.editor
    app.state.retriever = components.retriever

    email_channel = EmailChannel(
        EmailChannelConfig(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            sender=settings.smtp_from,
            start_tls=settings.smtp_start_tls,
        )
    )
    app.state.email_channel = email_channel
    app.state.usage_recorder = SessionUsageRecorder(app.state.session_factory)

    # 对话 Agent:工具循环(mid 档位)+ 每用户并发限流
    chat_registry = build_chat_registry(components.source_clients, components.fetcher)
    app.state.tool_loop = ToolLoop(
        components.provider,
        chat_registry,
        model=ModelTier.mid,
        max_iterations=settings.loop_max_iterations,
        total_timeout=settings.loop_total_timeout_seconds,
        max_context_chars=settings.loop_max_context_chars,
    )
    app.state.chat_limiter = UserConcurrencyLimiter(settings.chat_concurrency_limit)
    chat_prompt = (Path(__file__).parent.parent / "agents" / "prompts" / "chat.md").read_text(
        encoding="utf-8"
    )
    app.state.chat_system_prompt = chat_prompt + "\n\n可用工具:\n" + chat_registry.describe()

    def push_dispatch(push_log_id: int) -> object:
        return celery_app.send_task(PUSH_TASK, args=[push_log_id], queue="push")

    app.state.push_dispatch = push_dispatch

    yield

    await components.http_client.aclose()
    await redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="TradeWinds", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_v1_router)
    return app
