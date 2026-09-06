"""core/security:密码哈希与 JWT 编解码测试。"""

import pytest

from tradewinds.core.exceptions import AuthError
from tradewinds.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    hashed = hash_password("s3cret-password")

    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)


def test_verify_wrong_password_returns_false() -> None:
    assert not verify_password("wrong", hash_password("right"))


def test_token_round_trip() -> None:
    token = create_access_token(42, secret="secret", expires_minutes=5)

    assert decode_access_token(token, secret="secret") == 42


def test_expired_token_raises_auth_error() -> None:
    token = create_access_token(42, secret="secret", expires_minutes=-1)

    with pytest.raises(AuthError):
        decode_access_token(token, secret="secret")


def test_tampered_token_raises_auth_error() -> None:
    token = create_access_token(42, secret="secret", expires_minutes=5)

    with pytest.raises(AuthError):
        decode_access_token(token + "x", secret="secret")


def test_wrong_secret_raises_auth_error() -> None:
    token = create_access_token(42, secret="secret", expires_minutes=5)

    with pytest.raises(AuthError):
        decode_access_token(token, secret="other")
