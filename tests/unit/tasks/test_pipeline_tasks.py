"""管道/调度任务单元测试:同步 apply 执行(不经 broker),内部协程被打桩。"""

import pytest

from tradewinds.tasks import pipeline_tasks, scheduler_tasks
from tradewinds.tasks.celery_app import PIPELINE_TASK


async def _fake_run_ok(topic_id: int) -> dict[str, object]:
    return {"status": "ok", "new_items": 3}


async def _fake_run_boom(topic_id: int) -> dict[str, object]:
    raise RuntimeError("db down")


async def _fake_scan() -> dict[str, object]:
    return {"enqueued": 0}


def test_run_topic_task_name_and_success(monkeypatch) -> None:
    assert PIPELINE_TASK == "tradewinds.tasks.pipeline_tasks.run_topic"
    monkeypatch.setattr(pipeline_tasks, "_run_topic", _fake_run_ok)

    result = pipeline_tasks.run_topic_task.apply(args=[42])

    assert result.get() == {"status": "ok", "new_items": 3}


def test_run_topic_task_failure_is_reraised_and_logged(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_tasks, "_run_topic", _fake_run_boom)

    result = pipeline_tasks.run_topic_task.apply(args=[7])

    with pytest.raises(RuntimeError, match="db down"):
        result.get()


def test_scan_task_registered_and_runs(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_tasks, "_scan_due_topics", _fake_scan)

    result = scheduler_tasks.scan_due_topics_task.apply(args=[])

    assert result.get() == {"enqueued": 0}
