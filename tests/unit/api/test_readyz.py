"""/readyz 就绪检查测试:DB+Redis 连通 → 200,任一故障 → 503。

/healthz 只探进程存活;/readyz 探外部依赖,二者语义分离。
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from tradewinds.api.app import create_app


class FakeSession:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    async def execute(self, query: Any) -> None:
        if self._fail:
            raise SQLAlchemyError("db down")


class FakeSessionFactory:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    @asynccontextmanager
    async def __call__(self) -> Any:
        yield FakeSession(fail=self._fail)


class FakeRedis:
    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    async def ping(self) -> bool:
        if self._fail:
            raise ConnectionError("redis down")
        return True

    async def llen(self, key: str) -> int:
        return 0


def _client_with_state(session_fail: bool, redis_fail: bool) -> TestClient:
    app = create_app()
    app.state.session_factory = FakeSessionFactory(fail=session_fail)
    app.state.redis = FakeRedis(fail=redis_fail)
    return TestClient(app)


def test_readyz_ok_when_db_and_redis_reachable() -> None:
    client = _client_with_state(session_fail=False, redis_fail=False)

    response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"db": "ok", "redis": "ok"}
    assert body["queue_backlog"] == 0


def test_readyz_reports_db_failure() -> None:
    client = _client_with_state(session_fail=True, redis_fail=False)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["db"] == "fail"
    assert response.json()["checks"]["redis"] == "ok"


def test_readyz_reports_redis_failure() -> None:
    client = _client_with_state(session_fail=False, redis_fail=True)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["db"] == "ok"
    assert response.json()["checks"]["redis"] == "fail"
