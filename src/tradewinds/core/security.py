"""安全原语:bcrypt 密码哈希与 JWT 编解码。认证失败统一抛 AuthError。"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from tradewinds.core.exceptions import AuthError

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, *, secret: str, expires_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> int:
    """校验并解码 JWT,返回 user_id;无效/过期/密钥不符一律 AuthError(401)。"""
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise AuthError("无效或过期的凭证") from exc

    sub = payload.get("sub")
    if sub is None or not sub.isdigit():
        raise AuthError("无效或过期的凭证")
    return int(sub)
