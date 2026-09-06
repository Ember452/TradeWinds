"""Celery worker 入口:与 api 同镜像不同命令(compose: python -m tradewinds.tasks.worker)。"""

from tradewinds.core.config import get_settings
from tradewinds.core.error_tracking import init_error_tracking
from tradewinds.core.logging import setup_logging
from tradewinds.tasks.celery_app import celery_app, configure_broker


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    init_error_tracking(settings)
    configure_broker(celery_app, settings)
    celery_app.worker_main(
        ["worker", "--loglevel=INFO", "--concurrency=2", "-Q", "default,pipeline,push"]
    )


if __name__ == "__main__":
    main()
