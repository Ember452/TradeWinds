"""数据库引擎与会话工厂:统一在此创建,业务代码不自行 create_engine。"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """expire_on_commit=False:提交后对象仍可读,适配请求级会话。"""
    return async_sessionmaker(engine, expire_on_commit=False)
