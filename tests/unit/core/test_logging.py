"""setup_logging() 结构化日志测试。"""

import structlog

from tradewinds.core.logging import setup_logging


def test_setup_logging_configures_structlog() -> None:
    setup_logging()

    logger = structlog.get_logger("tradewinds.test")
    # 配置完成后应能正常输出而不抛异常;字段以 key-value 形式进入事件字典
    logger.info("hello", user_id=1)


def test_setup_logging_is_idempotent() -> None:
    setup_logging()
    setup_logging()
