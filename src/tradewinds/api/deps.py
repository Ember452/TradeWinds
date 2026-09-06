"""API 依赖注入:数据库会话、配置、当前用户、各服务实例。"""

from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.config import Settings, get_settings
from tradewinds.core.exceptions import AuthError, TradeWindsError
from tradewinds.core.security import decode_access_token
from tradewinds.models.user import User
from tradewinds.services.auth_service import AuthService
from tradewinds.services.chat_service import ChatService
from tradewinds.services.pipeline_service import PipelineService
from tradewinds.services.push_service import PushService
from tradewinds.services.rate_limit_service import RateLimitService
from tradewinds.services.report_service import ReportService
from tradewinds.services.topic_service import TopicService

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


def get_topic_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TopicService:
    return TopicService(
        session, request.app.state.planner, quota_topics_max=settings.quota_topics_max
    )


def get_pipeline_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PipelineService:
    push_service = PushService(
        session,
        request.app.state.email_channel,
        app_base_url=settings.app_base_url,
        dispatch=request.app.state.push_dispatch,
    )
    return PipelineService(
        session,
        request.app.state.retriever,
        request.app.state.analyst,
        request.app.state.editor,
        score_threshold=settings.pipeline_score_threshold,
        immediate_threshold=settings.push_immediate_threshold,
        suppress_hours=settings.push_cluster_suppress_hours,
        push_service=push_service,
        report_service=ReportService(session),
    )


def get_chat_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    return ChatService(
        session,
        request.app.state.tool_loop,
        system_prompt=request.app.state.chat_system_prompt,
        recorder=request.app.state.usage_recorder,
        limiter=request.app.state.chat_limiter,
    )


def get_rate_limit_service(request: Request) -> RateLimitService:
    return RateLimitService(request.app.state.redis)


def ip_rate_limit(scope: str) -> Callable[..., Awaitable[None]]:
    """注册/登录按 IP 限流依赖工厂;窗口与次数走配置,超限抛 429。"""

    async def dependency(
        request: Request,
        rate_limit_service: RateLimitService = Depends(get_rate_limit_service),
        settings: Settings = Depends(get_settings),
    ) -> None:
        client_ip = request.client.host if request.client else "unknown"
        allowed = await rate_limit_service.check(
            f"rl:{scope}:{client_ip}",
            limit=settings.auth_rate_limit_max,
            window_seconds=settings.auth_rate_limit_window_seconds,
        )
        if not allowed:
            raise TradeWindsError("请求过于频繁,请稍后再试", code="rate_limited", status_code=429)

    return dependency


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
