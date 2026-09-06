"""业务异常基类与统一错误码测试。"""

import pytest

from tradewinds.core.exceptions import AuthError, NotFoundError, QuotaExceededError, TradeWindsError


def test_base_error_carries_code_and_message() -> None:
    error = TradeWindsError("数据库连不上", code="internal_error")

    assert error.message == "数据库连不上"
    assert error.code == "internal_error"
    assert error.status_code == 500


def test_subclass_defaults() -> None:
    assert NotFoundError("主题不存在").code == "not_found"
    assert NotFoundError("主题不存在").status_code == 404

    assert AuthError("登录失败").code == "auth_failed"
    assert AuthError("登录失败").status_code == 401

    assert QuotaExceededError("主题数已达上限").code == "quota_exceeded"
    assert QuotaExceededError("主题数已达上限").status_code == 403


def test_subclass_can_override_status() -> None:
    # 注册时邮箱重复:语义属于认证域,HTTP 语义是 409
    error = AuthError("邮箱已注册", status_code=409)

    assert error.status_code == 409
    assert error.code == "auth_failed"


def test_subclass_is_base_error() -> None:
    with pytest.raises(TradeWindsError):
        raise NotFoundError("x")
