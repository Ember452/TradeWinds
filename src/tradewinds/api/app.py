"""FastAPI 应用工厂:所有路由经 create_app() 挂载。"""

from fastapi import FastAPI

from tradewinds.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="TradeWinds")
    app.include_router(health_router)
    return app
