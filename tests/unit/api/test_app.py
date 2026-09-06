"""create_app() 应用工厂冒烟测试。"""

from fastapi.testclient import TestClient

from tradewinds.api.app import create_app


def test_healthz_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
