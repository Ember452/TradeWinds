"""FastAPI 应用工厂:所有路由经 create_app() 挂载。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tradewinds.api.errors import register_exception_handlers
from tradewinds.api.health import router as health_router
from tradewinds.api.v1 import api_v1_router
from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    engine = create_engine(settings.database_url)
    app.state.session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="TradeWinds", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_v1_router)
    return app
