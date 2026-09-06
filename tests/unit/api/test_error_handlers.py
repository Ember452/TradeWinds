"""统一错误响应体 {code, message} 测试。"""

from fastapi.testclient import TestClient

from tradewinds.api.app import create_app
from tradewinds.core.exceptions import NotFoundError, TradeWindsError


def test_business_error_returns_unified_body() -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("主题不存在")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "主题不存在"}


def test_custom_status_override() -> None:
    app = create_app()

    @app.get("/conflict")
    async def conflict() -> None:
        raise TradeWindsError("冲突", code="conflict", status_code=409)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {"code": "conflict", "message": "冲突"}
