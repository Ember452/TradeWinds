# 幂等 upsert 与"以查询代替状态"

## 这个知识点是什么

幂等 upsert 指"同一份逻辑数据,执行一次和执行一百次,落库结果完全一致"的写入方式:不是靠先查后插的竞态侥幸,而是靠**数据库唯一约束 + 稳定的业务键**,让重复写入天然收敛到同一条记录。配套的思维是"以查询代替状态"——报告这类聚合物不保存"生成进度",每次需要时从源数据重算,源数据不变则结果不变。

类比:复印机不关心你按了多少次按钮,只要原稿没变,复印件永远一样;而"先查有没有复印过再印"的记账方式,两个人同时按键就会印出两份。

## TradeWinds 为什么需要它

周期报告由管道 run 触发,而 run 可能同周期发生多次(手动触发、beat 调度、甚至任务重跑)。扩展计划把它作为 M5 后第一个迭代,前提是不能给幂等性已经做好的管道引入"重复报告"这种新副作用。同时,报告内容依赖"周期内全部 accepted 条目",run 只带来增量——用"以查询代替状态"的思路,报告每次按周期桶全量重算,增量、乱序、重跑都不需要特殊处理。

## 本项目怎么实现的

- **唯一约束定身份**([models/report.py](../../src/tradewinds/models/report.py)):`(topic_id, period_type, period_start)` 唯一约束在数据库层宣告"一个主题一个周期只有一份报告"——这是幂等的最终防线,不依赖应用层判断;
- **周期桶是纯函数**([services/report_service.py](../../src/tradewinds/services/report_service.py)):`period_bounds(now, cadence)` 把任意时刻映射到固定边界(daily=UTC 日,weekly=ISO 周一),同一时刻永远得到同一个桶;
- **重算而非追加**:每次 `upsert_period_report` 查询周期内全部 accepted 条目,整体重渲染 Markdown,有则更新、无则插入;`updated_at` 由 `onupdate=func.now()` 维护;
- **分享 token 惰性生成**:`share()` 只在首次调用时生成 `secrets.token_urlsafe(16)`,重复调用复用同一 token——链接一旦发出不会失效,也不会越积越多。

## 踩过的坑

1. **`onupdate` 与手动赋值的时序**:SQLAlchemy 的 `onupdate=func.now()` 只在 UPDATE 语句包含该行其他字段变化时生效;纯"无变化提交"不会触发,好在测试断言的是内容而非 updated_at;
2. **周期桶必须用 UTC 定界**:本地时区(这台 Windows 是 +08:00)会让"哪一天"随服务器时区漂移,聚合边界一律 `datetime.replace(microsecond=0)` 前先转 UTC;
3. **mypy 对 `report.share_token is not None` 之后才放行**:`share()` 返回的对象 share_token 类型是 `str | None`,路由层直接赋给 `str` 会报错——用 `assert not None` 收窄,比 type: ignore 诚实。

## 延伸阅读

- [PostgreSQL: UNIQUE 约束](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-UNIQUE-CONSTRAINTS)——幂等写入的数据库层防线
- [SQLAlchemy ORM: onupdate](https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.Column.params.onupdate)——自动更新时间戳的触发条件
- [十二要素应用:幂等性相关实践](https://12factor.net/zh_cn/)——无状态与可重放的设计基调
