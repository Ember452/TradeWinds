"""structlog 结构化日志配置:全项目统一经 setup_logging() 初始化。"""

import logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    """初始化 structlog(JSON 输出,适配容器日志采集);可重复调用。"""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
