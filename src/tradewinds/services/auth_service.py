"""认证服务:注册、登录,JWT 签发。"""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.exceptions import AuthError
from tradewinds.core.security import create_access_token, hash_password, verify_password
from tradewinds.models.user import User


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthService:
    def __init__(self, session: AsyncSession, *, jwt_secret: str, jwt_expire_minutes: int) -> None:
        self._session = session
        self._jwt_secret = jwt_secret
        self._jwt_expire_minutes = jwt_expire_minutes

    async def register(self, email: str, password: str) -> User:
        """创建用户;邮箱已存在抛 AuthError(409)。邮箱统一小写存储。"""
        normalized = email.strip().lower()

        existing = await self._session.scalar(select(User).where(User.email == normalized))
        if existing is not None:
            raise AuthError("邮箱已注册", status_code=409)

        user = User(email=normalized, password_hash=hash_password(password))
        self._session.add(user)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            # 并发注册同一邮箱时,唯一约束兜底
            raise AuthError("邮箱已注册", status_code=409) from exc
        await self._session.refresh(user)
        return user

    async def login(self, email: str, password: str) -> TokenPair:
        """登录成功返回 token;失败统一 AuthError(401),不区分用户不存在/密码错误。"""
        normalized = email.strip().lower()
        user = await self._session.scalar(select(User).where(User.email == normalized))

        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("邮箱或密码错误")

        token = create_access_token(
            user.id, secret=self._jwt_secret, expires_minutes=self._jwt_expire_minutes
        )
        return TokenPair(access_token=token)
