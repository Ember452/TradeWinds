"""Celery 应用:队列路由、可靠性语义与 beat 调度。

模块导入不读取环境变量(测试可安全 import);broker/backend 由入口
(worker/beat/API lifespan)经 configure_broker 注入。
"""

from celery import Celery

from tradewinds.core.config import Settings

PIPELINE_TASK = "tradewinds.tasks.pipeline_tasks.run_topic"
SCAN_TASK = "tradewinds.tasks.scheduler_tasks.scan_due_topics"
PUSH_TASK = "tradewinds.tasks.push_tasks.send_push"
RECHECK_FEEDS_TASK = "tradewinds.tasks.feed_tasks.recheck_feeds"

_INCLUDE = [
    "tradewinds.tasks.pipeline_tasks",
    "tradewinds.tasks.scheduler_tasks",
    "tradewinds.tasks.push_tasks",
    "tradewinds.tasks.feed_tasks",
]


def create_celery_app(settings: Settings | None = None) -> Celery:
    app = Celery("tradewinds", include=_INCLUDE)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        # 可靠性:worker 崩溃时未确认任务重回队列;整任务重跑由管道指纹去重保证幂等
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_time_limit=900,
        task_soft_time_limit=780,
        task_default_queue="default",
        task_routes={
            PIPELINE_TASK: {"queue": "pipeline"},
            PUSH_TASK: {"queue": "push"},
        },
        beat_schedule={
            SCAN_TASK: {
                "task": SCAN_TASK,
                "schedule": 60.0,
                "options": {"queue": "default"},
            },
            RECHECK_FEEDS_TASK: {
                "task": RECHECK_FEEDS_TASK,
                "schedule": 86400.0,
                "options": {"queue": "default"},
            },
        },
    )
    if settings is not None:
        configure_broker(app, settings)
    return app


def configure_broker(app: Celery, settings: Settings) -> None:
    app.conf.update(broker_url=settings.redis_url, result_backend=settings.redis_url)


# 模块级单例:供 @celery_app.task 注册与 CLI 引用;broker 未配置前不发起连接
celery_app = create_celery_app()
