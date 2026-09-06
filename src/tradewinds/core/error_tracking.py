"""错误上报:Sentry 可选接入;未配置 DSN 时为空操作。

sentry-sdk 检测到 FastAPI/Starlette/Celery 已安装时自动启用对应集成,
无需显式传入;仅上报错误,不开启性能采样(阶段 0 不做链路追踪)。
"""

import sentry_sdk

from tradewinds.core.config import Settings


def init_error_tracking(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
    )
