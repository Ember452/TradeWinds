# SSE 流式与断连处理

## 这个知识点是什么

SSE(Server-Sent Events)是 HTTP 上的单向服务端推送:响应头 `text/event-stream`,服务端持续写出 `event:`/`data:` 帧,浏览器用 EventSource(或 fetch 流式读取)边收边渲染。相比 WebSocket,SSE 是纯 HTTP、单向、自动重连,天然适合"LLM 一个字一个字往外蹦"的场景。

"断连处理"是流式的另一半:客户端随时可能关页面/断网,服务端的生成器会在任意 await 点被取消。工程问题是——**被取消的那一瞬间,哪些事必须已经做完?哪些事还必须继续做完?**

类比:电话念稿子,听筒被挂断不影响你把稿子念完并归档——前提是"归档"这个动作不依赖对方在线。

## TradeWinds 为什么需要它

对话研究 Agent 的回答要跑工具循环(可能十几秒),用户等不了全量生成完再返回,所以 SSE 流式是体验刚需。而实施计划的验收标准明确要求:**客户端断连(CancelledError)→ 计量与落库仍完整(不丢引用)**。用户花了真金白银的 LLM token 和几十秒检索,不能因为最后一下断网就全部蒸发。

## 本项目怎么实现的

关键代码:[services/chat_service.py](../../src/tradewinds/services/chat_service.py) 与 [agents/orchestrator/sse.py](../../src/tradewinds/agents/orchestrator/sse.py)。

- **事件封装**:四类事件 `citations/delta/done/error`,统一渲染为 `event:` + 单行 JSON `data:`;
- **事件序保证**:先跑完工具循环 → 提取引用 → **先持久化 assistant 消息** → 再 yield `citations`(前端先渲染引用列表)→ delta 片段 → `done`(含 usage)。持久化先于流式输出,是"断连不丢"的第一道保险;
- **断连保护**:循环与落库放在 `asyncio.create_task` 的独立任务里,主协程 `await asyncio.shield(task)` 消费结果。客户端断连时,生成器被取消、`CancelledError` 原样上抛(不吞掉,让框架正常收尾),但**任务本身不受取消影响**,持久化与用量记录在后台完成;
- **`CancelledError` 不许吞**:整个链路上只有 `guarded_stream`(SSE 封装层)区分对待——普通异常转 `error` 事件,`CancelledError` 重新抛出。吞掉它会让断连看起来像"服务端正常结束",掩盖真实状态。

## 踩过的坑

1. **`asyncio.shield` 保护的是任务,不是 await**:外层被取消时 `await shield(...)` 本身仍抛 `CancelledError`——这正是我们要的(尽快释放连接),而任务继续跑;误以为 shield "不抛异常"就会写出吞取消的代码;
2. **流式响应里做 DB 写会拖慢首字节**:把持久化挪到循环完成时一次写入,而不是边流边写,避免了 delta 事件被事务延迟拖住;
3. **Caddy/Nginx 默认缓冲响应**:SSE 必须显式关缓冲(响应头 `X-Accel-Buffering: no`,Caddy 反代默认不缓冲),否则前端收到的是"一次性大块"而非流。

## 延伸阅读

- [MDN: Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)
- [Starlette: StreamingResponse](https://www.starlette.io/responses/#streamingresponse)——本项目 SSE 的载体
- [asyncio.shield 文档](https://docs.python.org/3/library/asyncio-task.html#asyncio.shield)——保护任务 vs 保护 await 的语义差异

---

## 2026-09 更新:真流式下的时序变化

本文"先持久化 → 再 yield citations → delta → done"的时序随真流式改造演进:持久化无法再先于流式(回答逐 token 生成中),改为循环事件经 `asyncio.Queue` 从后台任务转发给 SSE 生成器,citations 在首个 delta 前 flush(它来自工具轨迹,作答前已完整),持久化在流结束后一次写入。断连语义不变:取消只作用于 SSE 生成器,后台任务继续落库与计量;循环抛 `LLMError` 现在会转成 SSE `error` 事件而非静默断流。另外修正了一处潜在 bug:`set_rag_user` 原先在 `create_task` 之后才置入,contextvar 不会传给已创建的任务——现已移到任务创建前。见 [19-流式工具循环的决策与作答分离](19-流式工具循环的决策与作答分离.md)。
