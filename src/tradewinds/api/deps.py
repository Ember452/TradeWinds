"""API 依赖注入:数据库会话、配置、当前用户、认证服务。"""

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.config import Settings, get_settings
from tradewinds.core.exceptions import AuthError
from tradewinds.core.security import decode_access_token
from tradewinds.models.user import User
from tradewinds.services.auth_service import AuthService

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """请求级数据库会话:lifespan 建好的工厂放在 app.state。"""
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


def get_auth_service(
    session: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> AuthService:
    """每个请求新建服务实例,复用请求级会话。"""
    return AuthService(
        session, jwt_secret=settings.jwt_secret, jwt_expire_minutes=settings.jwt_expire_minutes
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """解析 Bearer token 并加载用户;缺失/无效/过期一律 401 统一错误体。"""
    if credentials is None:
        raise AuthError("缺少认证凭证")

    user_id = decode_access_token(credentials.credentials, secret=settings.jwt_secret)
    user = await session.get(User, user_id)
    if user is None:
        raise AuthError("无效或过期的凭证")
    return user
