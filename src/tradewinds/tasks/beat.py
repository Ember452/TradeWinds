"""Celery beat 入口:全局唯一调度者,只负责到点入队(compose: python -m tradewinds.tasks.beat)。"""

from tradewinds.core.config import get_settings
from tradewinds.core.error_tracking import init_error_tracking
from tradewinds.core.logging import setup_logging
from tradewinds.tasks.celery_app import celery_app, configure_broker


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    init_error_tracking(settings)
    configure_broker(celery_app, settings)
    celery_app.start(["beat", "--loglevel=INFO"])


if __name__ == "__main__":
    main()
