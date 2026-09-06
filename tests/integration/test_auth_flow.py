"""认证全链路集成测试:注册→登录→受保护端点→篡改 token。

标记 integration:CI 起 PostgreSQL service 运行;测试前需已跑 `alembic upgrade head`。
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tradewinds.api.app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    if "TRADEWINDS_DATABASE_URL" not in os.environ:
        pytest.skip("需要 TRADEWINDS_DATABASE_URL 指向真实 PostgreSQL")
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def email() -> str:
    return f"tw-{uuid.uuid4().hex[:12]}@example.com"


def test_register_login_protected_flow(client: TestClient, email: str) -> None:
    password = "s3cret-password"

    # 注册
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == email

    # 邮箱重复 → 409,统一错误体
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 409
    assert resp.json()["code"] == "auth_failed"

    # 密码错误 → 统一 401,不区分"用户不存在/密码错"
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth_failed"

    # 登录成功拿 token
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 带 token 访问受保护端点
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email

    # 篡改 token → 401
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}x"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth_failed"

    # 无 token → 401
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401
