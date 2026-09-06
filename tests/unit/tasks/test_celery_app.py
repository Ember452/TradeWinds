"""Celery 应用配置测试:队列路由、可靠性语义、beat 调度;导入不依赖环境变量。"""

from tradewinds.core.config import Settings
from tradewinds.tasks.celery_app import (
    PIPELINE_TASK,
    PUSH_TASK,
    SCAN_TASK,
    create_celery_app,
)


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost:5432/tw",
        redis_url="redis://localhost:6379/0",
        jwt_secret="s",
        llm_api_base="https://llm.test/v1",
        llm_api_key="k",
        model_low="low",
        model_mid="mid",
    )


def test_create_celery_app_routes_by_queue() -> None:
    app = create_celery_app()

    routes = app.conf.task_routes
    assert routes[PIPELINE_TASK] == {"queue": "pipeline"}
    assert routes[PUSH_TASK] == {"queue": "push"}
    assert app.conf.task_default_queue == "default"


def test_reliability_semantics() -> None:
    app = create_celery_app(_settings())

    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.task_time_limit == 900


def test_beat_schedules_scan_every_minute() -> None:
    app = create_celery_app()

    entry = app.conf.beat_schedule[SCAN_TASK]
    assert entry["schedule"] == 60.0


def test_configure_broker_sets_urls() -> None:
    app = create_celery_app(_settings())

    assert app.conf.broker_url == "redis://localhost:6379/0"
    assert app.conf.result_backend == "redis://localhost:6379/0"


def test_module_import_is_env_free() -> None:
    # 单例已被 task 模块 import;若模块级读环境变量,无 env 的 CI 单元 job 会炸
    from tradewinds.tasks.celery_app import celery_app

    assert celery_app.main == "tradewinds"
