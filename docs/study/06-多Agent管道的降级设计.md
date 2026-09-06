# 多 Agent 管道的降级设计

## 这个知识点是什么

多 Agent 管道把一次任务拆成多个角色接力(检索→评分→摘要→落库)。降级设计的核心思想:链条上任何一环的外部依赖(某个信息源、LLM 的一次调用)失败时,系统**带着可见的缺口继续完成主流程**,而不是整体报错。前提是每个环节的失败都是"信息缺失",不是"数据污染"。

类比:食堂打饭流程里,某个菜卖完了(降级标记),师傅照常打其余的菜,并在窗口贴张纸条;而不是因为缺一个菜让整个窗口关门。

## TradeWinds 为什么需要它

一次 run 要访问 3 个外部源 + 2 次档位的 LLM。信息源的可用性从来不受我们控制(HN 限流、arXiv 维护),如果任何单源失败就让整次 run 报错,用户会看到"定期任务天天失败",但实际 90% 的数据是好的。design.md 4.1 的原则:**Agent 工具失败作为结果回注/降级标注,而非中断**。

## 本项目怎么实现的

- **源级降级**:`Retriever.collect` 用 `asyncio.gather` 并发调源,每个源被 `_safe_search` 包裹:异常被捕获,记 `source_degraded` warning 日志,以 `SourceDegraded(source, reason)` 出现在 `CollectResult.degraded`,管道末尾再汇总一次 warning;
- **条目状态机**:items 表状态 `pending → scored → accepted | rejected`。评分低于 `TRADEWINDS_PIPELINE_SCORE_THRESHOLD`(暂定 6 分)置 rejected、不进 Editor——"降级"不只是故障,还包括"质量不够就不打扰用户";
- **幂等与去重**:入库前按 `sha256(规范化 url|topic_id)` 指纹过滤,重复 run 天然幂等;Analyst 没覆盖到的条目计 0 分进 `unmatched` 聚类,不会悬空;
- **可观测**:`pipeline_run`/`source_degraded` 两条结构化日志是排查的首选入口,`PipelineResult` 把各阶段计数返回给 API 调用方。

## 踩过的坑

1. **"先落库再加工"的中间态**:候选先以 `pending` 状态入库,后续评分/摘要是同一事务里的 UPDATE。如果反过来"全部加工完再入库",一次 Editor 失败会丢掉已拿到的数据;
2. **Session 生命周期**:管道跨多个 await,会话必须覆盖全程但不能跨请求复用——FastAPI 依赖 `get_db` 的 `async with factory()` 保证请求结束即归还;
3. **测试里替换组件**:集成测试通过替换 `app.state.planner/retriever/analyst/editor` 为假件来跑全链路,前提是依赖注入只从 `app.state` 读组件、不在路由内new——这反过来约束了组装必须集中在 lifespan。

## 延伸阅读

- [Google SRE: Cascading failures 与 graceful degradation](https://sre.google/sre-book/handling-overload/)——降级与过载保护的工程视角
- [SQLAlchemy AsyncIO](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)——async 会话与事务边界
