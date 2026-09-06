# TradeWinds Agent 体验升级实施计划书

> **For agentic workers:** 按任务顺序执行,每 Task 走 TDD 固定循环(写失败测试 → 最小实现 → 通过 → lint/mypy 零错误)。本计划不提交 commit,由用户审阅后决定。

**Goal:** 消除对话 Agent 的四处"demo 级"简化:伪流式、引用无校验、web_search 缺失(文档与代码不一致)、即时推送纯规则无 LLM 判断。对标 flow-agent / akashic-agent 的同类能力(真流式回复、LLM Judge 推送守门、主动推送深度),按 TradeWinds 的产品形态(FastAPI + Celery 多用户 Web 服务)取精简版实现。

**Spec:** [docs/design.md](../design.md) v0.3 §4(Agent 编排)、§10(G1 引用交付物);本文档锁定接口契约与验收标准。

**背景**:对比调研结论(2026-09-06):持久化/队列/计量等骨架已是真实实现,demo 感集中在 Agent 体验层。设计文档三处需同步:§10 中 web_search"暂缓"取消、G1 引用校验补全、推送 Judge 增补。

---

## Task A 对话真流式(决策 + 流式作答两阶段循环)

**问题:** `chat_service.py` 先等整段 LLM 生成完,再 `chunk_text` 切成 80 字符假 delta——用户要等全部生成完才见第一个字。`provider.stream` 契约已定义但无人使用。

**方案:** 工具循环拆为两阶段,保持"结构化输出决策、不用 SDK 原生 tool_calls"的既有架构决策(docs/study/03):

- **决策轮:** `provider.complete(response_model=LoopDecision)`,`LoopDecision = {"tool_calls": [...]}`;空 `tool_calls` = 信息足够、请求作答。schema 强制保证决策形态,不依赖 prompt 自觉。
- **作答轮:** 决策为空后,循环追加一条作答指令消息,走 `provider.stream` 真·文本流,增量经循环事件透出。

**Interfaces:**

- `llm.py`:`StreamEvent(delta: str = "", usage: Usage | None = None)`,`stream() -> AsyncIterator[StreamEvent]`(契约从 `AsyncIterator[str]` 演进;最后一个事件带 usage,供应商不支持 `stream_options.include_usage` 时 usage 为 None,该次调用计量记 0 并降级)。实现层带一次 `BadRequestError` 回退(去掉 stream_options 重试)。
- `loop.py`:`LoopDecision(tool_calls: list[ToolCallRequest] = [])` 取代 `AssistantTurn` 作决策 schema;新增事件模型 `ToolTraceEvent(trace)` / `AnswerDeltaEvent(text)` / `LoopDoneEvent(result)`;
  - `ToolLoop.run_streaming(messages) -> AsyncIterator[LoopEvent]`:工具轨迹事件 → 作答增量事件 → 结束事件;超时/流中断时作答增量已在手的,结束事件带部分内容(`stopped_reason="timeout"`;新增 `"stream_interrupted"` 表示流中途 LLM 异常,半截回答 + 截断说明)。
  - `ToolLoop.run(messages) -> LoopResult` 保留:内部消费 `run_streaming`,供非流式调用方与旧测试。
  - `AssistantTurn`、`chunk_text`/`_DELTA_CHUNK_CHARS` 随本次改动失效,删除(含对应测试)。
- `chat_service.py`:`_respond` 改为后台任务消费 `run_streaming` 事件 → `asyncio.Queue` 转发 SSE;**事件序保持 citations → delta* → done**(引用来自工具轨迹,作答前已完整,前端零改动)。客户端断连时后台任务继续完成持久化与计量(study 08 语义不变)。循环抛 `LLMError` 时发 SSE `error` 事件而非静默断流。
- `prompts/chat.md`:改写为两阶段协议说明(决策 JSON / 自然语言作答),引用规范不变,补充 web 源选择指引。

**验收要点:** 单测:事件序(工具轨迹先于作答增量)、usage 聚合(决策轮 + 作答流)、超时返回部分内容、`run()` 与 `run_streaming()` 结果一致;集成测试 `FakeToolLoop` 改实现 `run_streaming`,断言 citations 先行与落库。

## Task B 引用校验

**问题:** 引用是从工具轨迹正则抓 URL 按序编号,回答中 `[n]` 与引用列表是否对应无任何校验(G1 的唯一缺口);模型幻觉编号(如 `[9]` 超界)会原样展示。

**方案:** 回答完成后校验(作答前无法知道模型会引用哪些编号):

- `chat_service.verify_citations(answer, citations) -> (cleaned_answer, kept_citations)`:剔除越界/无来源的 `[n]` 标记;仅保留回答实际引用过的编号进持久化(直播 SSE 的 citations 事件仍发全量来源列表——作答前无法预知引用集合,直播视图=来源列表、刷新后=实际引用,差异记录于 study 文档)。
- 剔除越界编号时记 structlog warning `citation_invalid_reference`;已知局限:编号合法但内容无中生有的引用无法检测(prompt 层约束),记入 study 已知边界。
- 持久化 content 用清理后的文本(刷新后无悬空标记)。

**验收要点:** 单测:越界编号剔除、未引用条目不进持久化列表、无 `[n]` 时持久化引用为空、合法编号原样保留。

## Task C web_search 通用搜索

**问题:** `prompts/planner.md` 允许选 `web` 源,但 `tools/` 下没有对应客户端,选了就静默缺源(design.md §10 自认"暂缓"但 prompt 未同步)。

**方案:** `tools/websearch.py` 实现 `WebSearchClient(name="web")`,DuckDuckGo HTML 端点(`html.duckduckgo.com/html/?q=`),零新依赖(httpx + stdlib html.parser):

- 解析 `result__a` 标题链接 + `result__snippet` 摘要,解开 `uddg=` 跳转参数得真实 URL,过滤站内广告(`y.js`);`raw_content` 存摘要文本。
- 管道侧:注册进 `runtime.py` 的 `source_clients`,与其他客户端同构(源选择过滤在客户端内部:`self.name not in plan.sources` 返回空)。**注意:本机网络不可达 DuckDuckGo,契约测试固件为按其稳定 HTML 结构手工构造的样例,线上行为待有网环境验证一次**——记入计划实施记录。
- 对话侧:`build_chat_registry` 自动获得 `search_web` 工具(与 `search_arxiv` 同构);`prompts/chat.md` 补 web 源说明。
- design.md §10 取消"暂缓"标注。

**验收要点:** 契约测试(固件解析:标题/URL 解码/摘要/广告过滤/数量上限);源选择过滤(未选 web 时返回空);对话注册表含 `search_web`。

## Task D 即时推送 LLM Judge

**问题:** 即时推送是纯规则(阈值 + 聚类抑制),分数高≠值得打断用户。对标 flow-agent 的 judge loop / akashic 的电量模型,取精简版:推送前低档 LLM 逐条判断 push/skip。

**方案:**

- `agents/prompts/push_judge.md` + `agents/push_judge.py`:`PushJudge.decide(topic, items, *, preferences) -> dict[url, ItemPushDecision]`,一次 LLM 调用批量判定(`PushJudgement = {"decisions": [{url, push, reason}]}`),low 档位,role=`push_judge` 入计量。判定标准:与主题相关性标准的契合度、新颖性、打断成本;宁缺毋滥。
- **失败开放(fail-open):** Judge 调用失败(含无 LLM key)记 warning 并跳过判定、全部照旧推送——LLM 故障不改变既有推送行为。
- `PipelineService` 增可选参数 `push_judge`;`high_score` 非空且 judge 在位时先判定再进 `prepare_immediate`。
- `PushService.prepare_immediate` 增可选 `judgements`:被判 skip 的条目建 `PushLog(status=skipped, judge_reason=原因)` 不入队(审计留痕;`item:<id>` 去重键同时避免同一 item 反复送判),照推的条目 `judge_reason` 记判定理由。**迁移 0011:push_logs 增 `judge_reason TEXT NULL`。**
- 接线:`PipelineComponents` 增 `push_judge` → `app.state.push_judge` → `deps.get_pipeline_service` 与 `tasks/pipeline_tasks` 两处注入;集成测试 fixture 替换为假 judge。

**验收要点:** 单测:批量判定解析、失败开放、skip 不入队但落 skipped 日、push 记录理由;集成:管道 run → judge 被调用 → 理由落库;迁移链 0001-0011 完整。

---

## 明确不做(对标后主动放弃)

- flow-agent / akashic 的 DDD 分层、双总线、插件拓扑排序、多渠道接入(Telegram/QQ)——围绕"单用户常驻 IM 进程"设计,与本项目多用户 Web 形态不匹配。
- 记忆系统全家桶(sqlite-vec + HyDE + RRF + prompt cache 缓冲)——单次会话研究场景收益有限,现有 SQL 画像先保留,单独立项。
- 评测在线化(金标集真 LLM 回放)、Editor 并发化、成本金额换算、coverage 硬门禁——后续独立计划,不混入本次。

## 文档同步

- `docs/design.md`:§10 web_search 取消暂缓、推送 Judge 增补、G1 引用校验落地标注。
- `docs/architecture.md`:§5 模块清单增 `tools/websearch.py`、`agents/push_judge.py`;LLMProvider.stream 契约更新为 StreamEvent;ToolLoop 两阶段说明。
- `docs/study/19-流式工具循环的决策与作答分离.md`(新);03/08 尾部追加"2026-09 更新"说明设计演进。

## 实施记录(2026-09-06 交付)

- Task A:`StreamEvent` 契约(`llm.py`,含 stream_options 不支持的 BadRequestError 降级);`loop.py` 重写为两阶段(`LoopDecision` 决策 + `provider.stream` 作答,事件模型 `ToolTraceEvent/AnswerDeltaEvent/LoopDoneEvent`,`run()` 消费 `run_streaming`);`chat_service` 改队列转发(事件序 citations→delta*→done 保持,前端零改动;`LLMError` 转 SSE error 事件);`chat.md` 改写为两阶段协议;`AssistantTurn`/`chunk_text` 删除。**顺手修正一个潜在 bug**:`set_rag_user` 原先在 `create_task` 之后置入,contextvar 不进任务上下文,后台任务里的 RAG 历史检索拿不到用户标识——现移至任务创建前(study 08 更新)。
- Task B:`verify_citations` 剔除越界 `[n]`、持久化只留实际引用;直播 citations 事件仍发全量来源列表(作答前不可知引用集合),直播/刷新视图差异记入 study 19。
- Task C:`tools/websearch.py`(DDG html 端点,stdlib html.parser,零新依赖),注册进 runtime(管道按 plan.sources 自过滤,对话自动获得 `search_web` 工具)。**固件为手工构造**(本机网络不可达 DuckDuckGo),线上结构变化需以真实页面回填验证一次。
- Task D:`agents/push_judge.py` + prompt(low 档,批量判定,fail-open);`pipeline_service` 阈值过滤后送判;`prepare_immediate` 增 `judgements`(skip 建 `PushLog(status=skipped, judge_reason=...)` 不入队,item 级去重键同时防反复送判);迁移 `0011_push_judge_reason`;runtime/app.state/deps/pipeline_tasks 四处接线;两个集成测试 fixture 补假 judge,新增 judge-skip 审计用例。

## 验收

- [x] 单测(178)+ 契约测试、ruff、mypy(strict)全绿;集成测试本机无 Docker 跳过,待 CI 确认
- [x] 前端零改动(事件序兼容),SSE 消费逻辑无差异
- [x] design.md / architecture.md / study 03/08 更新 + 新增 study 19
- [ ] WebSearchClient 线上冒烟(待有网环境)
- [ ] 未提交 commit,待用户审阅
