# Celery 任务幂等与重试语义

## 这个知识点是什么

Celery 是 Python 生态最常用的分布式任务队列:业务进程把"要做的事"发消息到队列(Redis),worker 进程取出来执行。定时调度由 beat(独立进程,按表触发)承担。两个关键词:**幂等**——同一任务执行多次结果不变、无副作用累积;**重试语义**——任务失败后谁负责再试、隔多久、试几次、失败状态落在哪。

类比:队列像外卖接单池,"幂等"是重复接同一单只做一次餐;"重试语义"是骑手超时后系统自动再派,派满三次就标记异常单让你人工处理,而不是无限重派。

## TradeWinds 为什么需要它

订阅主题按 daily/weekly 频率自动执行,靠的是 beat 每分钟扫描"到期主题"并入队;一次管道要跑几十秒,绝不能占用 API 进程(api 只处理同步请求)。而队列系统的默认行为恰恰是"尽力而为":worker 崩溃时任务可能丢,自动重试又可能造成重复执行——所以幂等与重试语义必须**显式设计**,不是配置一项就完事。

## 本项目怎么实现的

关键代码:[tasks/celery_app.py](../../src/tradewinds/tasks/celery_app.py) 与 [tasks/pipeline_tasks.py](../../src/tradewinds/tasks/pipeline_tasks.py)。

- **可靠性**:`task_acks_late=True` + `task_reject_on_worker_lost=True`(worker 崩溃时任务重回队列)+ `worker_prefetch_multiplier=1`(防止单 worker 攒任务饿死别人);任务级超时 900s 兜底;
- **幂等**:不依赖 Celery 的去重(它没有),靠业务实现——items 表的 `url_hash` 主题内唯一约束,任务重跑时老条目全部被指纹过滤,Analyst/Editor 只处理新增条目。因此 `run_topic_task` 设 `max_retries=0`:失败不自动重试,下次调度或手动触发天然就是"重试";
- **去重调度**:beat 任务用 Redis 锁(`SET NX`,`timeout=55s < 调度间隔 60s`)保证多实例部署时每分钟只有一个实例扫描入队;
- **队列分工**:`default`(调度)/`pipeline`(管道,重)/`push`(推送)三队列路由,权重不同的任务互不阻塞;
- **分层**:任务层(`tasks/`)只做"编排与执行环境"(自建事件循环、会话、组件),业务在 services——所以任务薄到可以用 `.apply()` 同步测试,不需要 broker。

## 踩过的坑

1. **Celery 应用模块导入读环境变量会炸测试**:模块级 `get_settings()` 在 CI 无 env 的单元 job 直接 ValidationError。方案:Celery 实例保持"裸"配置,broker 经 `configure_broker(settings)` 由 worker/beat/API 入口注入;
2. **任务内跑 async 代码**:Celery worker 是同步世界,管道全是 async。用 `asyncio.run(_coro())` 在任务内自建事件循环,同时必须自建 DB engine/会话——asyncpg 连接绑定循环,不能跨循环复用全局对象;
3. **`self.retry()` 是靠抛异常实现的**:在 `except` 里调 `self.retry()` 后代码不会继续走;重试耗尽时 Celery 抛 `MaxRetriesExceededError`,要把"最终失败"落到 push_log 之类的可查询载体,而不是只留日志。

## 延伸阅读

- [Celery 官方: Tasks 最佳实践](https://docs.celeryq.dev/en/stable/userguide/tasks.html)——acks_late 与重试语义的权威说明
- [Celery: Periodic Tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html)——beat 调度与单实例问题
- [孙志辉: 分布式任务队列的幂等设计](https://stackoverflow.com/questions/14236101/celery-task-idempotency)——社区对"队列层无去重"的共识与业务层方案
