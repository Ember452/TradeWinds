"""认证请求模型约束测试:密码强度最低 8 位。"""

import pytest
from pydantic import ValidationError

from tradewinds.api.v1.auth import RegisterRequest


def test_password_below_8_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", password="a1b2c3d")


def test_password_8_chars_accepted() -> None:
    request = RegisterRequest(email="user@example.com", password="a1b2c3d4")

    assert request.password == "a1b2c3d4"
