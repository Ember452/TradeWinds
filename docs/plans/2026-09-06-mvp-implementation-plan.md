# TradeWinds MVP 实施计划书

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付可真实运营的 TradeWinds MVP——主题订阅检索管道、Feed、邮件推送、对话研究 Agent 与 React 前端，单 VPS 上线。

**Architecture:** FastAPI（api/worker/beat 三容器）+ PostgreSQL + Redis + Celery + 自研 Agent 编排层（工具循环/结构化输出/流式）+ React SPA。运行时与包结构见 [architecture.md](../architecture.md)。

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2.0 async · Alembic · Celery · Redis · httpx · OpenAI-compatible SDK · React/Vite/TS · Docker Compose · Caddy

**Spec:** [docs/design.md](../design.md) v0.2 —— 本计划从 spec 出发，执行者两份都要读。

**计划约定：**

- 本计划锁定**接口契约、模块范围、验收标准**；不锁定具体文件名与代码级设计——每个 Task 的范围只写到目录/模块级，文件怎么拆按 AGENTS.md 第 6 节的拆分信号在实现时决定
- 每个 Task 内部按 TDD 固定循环执行：**写失败测试 → 跑确认失败 → 最小实现 → 跑通过 → lint + mypy 零错误 → 写 docs/study/ 学习文档（AGENTS.md 第 10 节格式）→ Commit**
- 下文各 Task 只列差异信息（范围、接口契约、验收要点、特殊步骤），不重复循环模板

## Global Constraints（每个 Task 隐含遵守）

- Python 3.13，src layout；依赖方向与命名规范见 architecture.md 第 2/4 节，违反即返工
- 全量类型标注，`mypy` 与 `ruff check` 零错误；测试中所有 LLM/网络调用一律 mock，测试不依赖外网
- 配置一律 `pydantic-settings` 读取（前缀 `TRADEWINDS_`），新增配置必须同步 `.env.example`
- DB 变更只经 Alembic 迁移；迁移只进不退
- LLM 分档：`ModelTier.low`（Planner/Retriever/Analyst）与 `ModelTier.mid`（Editor/对话）；代码不出现供应商型号字符串
- 提交遵循 AGENTS.md 第 8 节 Conventional Commits；每 Task 提交一次（含对应 study 文档）
- 一期范围不含：周期报告生成、主动推送阈值、用户记忆、自定义 RSS（design.md 第 10 节）

---

## Phase 1：可上线的空壳（对应里程碑 M1）

**交付判据**：`docker compose up` 起完整栈，浏览器可注册登录，`/readyz` 绿，CI 从 PR 到镜像构建全通。

### Task 1.1 工程骨架与工具链

**范围：** `pyproject.toml`（ruff/mypy/pytest/coverage 配置唯一来源）、`Makefile`、`.env.example`、pre-commit、CI workflow（lint/type/test + 集成测试 job）、应用工厂 `create_app()` 与 `/healthz`、冒烟测试
**Produces:** `create_app() -> FastAPI`（后续所有路由经此挂载）；Makefile 目标 `lint/type/test/dev`
**验收要点:** `ruff check`、`mypy src`、`pytest` 三条命令零错误；CI 在 PR 上跑同样三条 + 起 postgres/redis service 的集成测试 job；pre-commit 安装成功
**Commit:** `chore: 工程骨架与工具链`

### Task 1.2 核心配置、日志与异常基类

**范围：** `core/`（Settings、structlog 配置、异常基类）+ 单元测试
**Produces:** `get_settings() -> Settings`（缓存单例；字段含 database_url、redis_url、jwt_secret、jwt_expire_minutes、model_low、model_mid、llm_api_base、llm_api_key、`quota_topics_max: int = 5`）；`setup_logging()`；`TradeWindsError(msg, code)` 与 `NotFoundError`/`AuthError`/`QuotaExceededError`
**验收要点:** 缺必填配置时启动即 fail-fast 并报出明确缺失项；Settings 字段全部有注释并同步 `.env.example`；异常子类携带稳定错误码，全局错误响应体统一为 `{code, message}`
**Commit:** `feat(core): 配置、结构化日志与异常基类`

### Task 1.3 数据库基线与 users 表

**范围：** `core/` DB 会话工厂、`models/` 基类与 User、Alembic 初始化（async 模板）与首个迁移、迁移集成测试
**Produces:** `async_session_factory`；`User` 模型（email 唯一、password_hash、notify_email、quota_topic_max、created_at）
**验收要点:** 集成测试在真实 PG 上跑 `alembic upgrade head` 断言表结构，down 可回退；模型表名为复数
**Commit:** `feat(models): 数据库基线与 users 表`

### Task 1.4 注册登录（JWT）

**范围：** `core/` 安全模块（bcrypt、JWT）、`services/` 认证服务、`api/` 认证路由与依赖注入（get_db / get_current_user）、单元 + 集成测试
**Interfaces (Produces):** `AuthService.register(email, password) -> User`（邮箱重复抛 `AuthError(409)`）；`AuthService.login(email, password) -> TokenPair`；`get_current_user` 依赖（无效/过期 JWT → 401 统一错误体）
**验收要点:** 密码强度最低 8 位；登录失败统一 401 不区分"用户不存在/密码错"；集成测试覆盖 注册→登录→带 token 访问受保护端点→篡改 token 401
**Commit:** `feat(auth): 注册登录与 JWT`

### Task 1.5 Redis 接入与 IP 限流

**范围：** `core/` Redis 工厂、`services/` 限流服务、登录/注册路由接入限流、单元 + 集成测试
**Interfaces (Produces):** `RateLimitService.check(key: str, limit: int, window_seconds: int) -> bool`（INCR+EXPIRE 原子实现）
**验收要点:** 注册/登录按 IP 限流（窗口与次数走配置）；Redis 不可用时**放行并告警日志**（限流是保护措施，不因它停服）
**Commit:** `feat(core): Redis 接入与 IP 限流`

### Task 1.6 Docker Compose 与 HTTPS 部署

**范围：** 多阶段 Dockerfile（非 root 运行）、`docker-compose.yml`（api/postgres/redis/caddy + 健康检查 + 依赖条件）、`deploy/`（HTTPS 入口配置、生产覆写）
**验收要点:** `make up` 一条命令起全栈；`/healthz`（进程存活）与 `/readyz`（DB+Redis 连通）语义分离；容器非 root 运行
**Commit:** `chore(deploy): Compose 全栈与 Caddy HTTPS`

### Task 1.7 CI/CD 与首次上线

**范围：** 部署 workflow（main 合并 → 构建镜像 → SSH 拉取并滚动重启 → 跑迁移）
**验收要点:** 部署每一步失败即中断且不破坏旧版本（先 pull 后切换）；真实域名 HTTPS 可访问；README 增加在线地址
**Commit:** `ci: 构建与部署流水线，空壳上线`
**学习文档建议:** `01-工程骨架：pyproject 统一配置`、`02-JWT 在无状态 API 中的使用`

---

## Phase 2：Agent 管道核心（对应里程碑 M2）

**交付判据**：创建主题后手动触发，数据库出现带评分、摘要、原文链接的条目；单源故障不影响出报。本期全部离线可测（mock LLM + 录制固件）。

### Task 2.1 topics 与 items 表

**范围：** `models/` Topic 与 Item、迁移、集成测试
**Produces:** `Topic`（name/description/plan JSONB/cadence enum daily|weekly/status/last_run_at/next_run_at）、`Item`（source/url/url_hash 主题内唯一/title/raw_content/published_at/score/cluster_key/summary/reason/status enum pending→scored→accepted|rejected）——字段在迁移设计时定稿，此处为契约语义
**验收要点:** url_hash 主题内唯一约束；支持按 next_run_at 批量扫描到期主题；长文本截断有统一工具函数
**Commit:** `feat(models): 主题与条目模型`

### Task 2.2 编排层：LLMProvider 与计量

**范围：** `agents/orchestrator/` LLM 抽象与计量模块 + 单元测试
**Interfaces:** 见 architecture.md 第 5 节 `LLMProvider`；`MeteringRecorder.record(user_id, role, tier, usage) -> None`（先落结构化日志，Phase 3 起落库）
**验收要点:** 基于 OpenAI-compatible SDK，base_url/model 全部来自 Settings；429/5xx 指数退避重试（上限 3 次）；`response_model` 路径返回经校验的 `LLMResult[T]`（含 usage）；测试全部 mock SDK
**Commit:** `feat(agents): LLMProvider 抽象与计量`

### Task 2.3 编排层：结构化输出执行器与工具循环

**范围：** `agents/orchestrator/` 结构化输出执行器、工具循环执行器、SSE 事件流封装 + 单元测试
**Interfaces:** `StructuredRunner.run(prompt, response_model) -> T`（校验失败把校验错误回注重试，上限 2 次）；`ToolLoop.run(messages) -> LoopResult`（见 architecture.md 第 5 节；`max_iterations=10`、`total_timeout=120s` 走配置）；SSE 事件封装（delta/citations/done/error 四类）
**验收要点（自研三风险，必须各有测试）:** ①上下文超长按"保系统指令+最近工具结果"截断 ②工具抛异常 → 错误作为工具结果回注模型、循环继续 ③SSE 生成器中途抛错 → 客户端收到 error 事件而非连接静默断开
**Commit:** `feat(agents): 结构化输出执行器与工具循环`
**学习文档建议:** `03-自研 Agent 工具循环`、`04-结构化输出校验重试`

### Task 2.4 Planner：主题编译

**范围：** `agents/schemas/` 检索计划模型、`agents/prompts/` planner prompt、`agents/` Planner 模块、金标集目录与评测测试
**Interfaces:** `Planner.compile(description: str, cadence) -> RetrievalPlan`（字段：keywords、sources、arxiv_categories、github 查询参数、window_days、relevance_criteria——对齐 design.md 4.2 示例）
**Produces（金标集机制，长期使用）:** ≥10 个"描述→计划要点"用例；测试断言关键词覆盖与源选择，不逐字比对
**验收要点:** prompt 独立文件加载；schema 校验失败自动重试（复用 2.3）；金标集测试 CI 必跑
**Commit:** `feat(agents): Planner 主题编译与金标集`

### Task 2.5 信息源客户端（arXiv / HN / GitHub / 通用抓取）

**范围：** `tools/` 客户端协议与公共工厂、三个源客户端、通用网页抓取 + 正文提取、契约测试与录制固件
**Interfaces:** 见 architecture.md 第 5 节 `SourceClient`；`CandidateItem`（source/url/title/published_at/raw_content）；`Fetcher.fetch(url) -> ExtractedContent`
**验收要点:** 每个源 ≥3 条录制固件的契约测试（正常/空结果/畸形响应）；客户端内置速率控制（信号量 + 请求间隔）；`search` 内部用 `seen_hashes` 过滤已见 URL（指纹 = sha256(规范化 url) + topic_id，实现放协议公共模块）
**Commit:** `feat(tools): 三个信息源客户端与网页抓取`
**学习文档建议:** `05-异步并发抓取与速率控制`

### Task 2.6 Retriever 与 Analyst

**范围：** `agents/` Retriever、Analyst 模块、analyst prompt、评分 schema、单元测试
**Interfaces:** `Retriever.collect(plan, seen_hashes) -> list[CandidateItem]`（并发各源；单源异常记 warning 并标注降级，不上抛）；`Analyst.score(items, topic) -> list[ScoredItem]`（0-10 分 + 聚类键；低价位模型、raw_content 先截断）
**验收要点:** mock 一个源抛异常 → 其余源条目正常产出且带降级标记；低于阈值条目状态置 rejected，不进 Editor
**Commit:** `feat(agents): Retriever 并发检索与 Analyst 评分聚类`

### Task 2.7 Editor 单条摘要与管道集成

**范围：** `agents/` Editor 模块与 prompt、`services/` 条目落库、管道编排入口、主题服务、`api/v1/` 主题路由、集成测试
**Interfaces:** `Editor.summarize(item, topic) -> ItemDigest`（summary + reason）；`PipelineService.run_topic(topic) -> PipelineResult`（编排 Retriever→Analyst→Editor→落库，返回各阶段计数）；REST：`POST /api/v1/topics`（返回 Planner 计划预览）、`GET/PATCH/DELETE /topics/{id}`、`POST /topics/{id}/run`（受配额限制）
**验收要点:** 集成测试：建主题（mock Planner）→ run（mock 全部源与 LLM）→ 断言 items 落库、状态流转正确、重复 run 不产生重复条目；配额满抛 `QuotaExceededError`
**Commit:** `feat(pipeline): 订阅检索管道与主题 API`
**学习文档建议:** `06-多 Agent 管道的降级设计`

---

## Phase 3：订阅闭环（对应里程碑 M3）

**交付判据**：主题按频率自动执行，Feed 可分页读取，邮箱收到汇总邮件；队列可观测。

### Task 3.1 Celery 接入与定时调度

**范围：** `tasks/` Celery 应用工厂、管道任务、beat 调度配置；compose 增 worker/beat 容器；集成测试
**Interfaces:** `run_topic_task(topic_id) -> dict`（任务名 `tradewinds.tasks.<模块>.run_topic`，入 `pipeline` 队列；acks_late + 任务级超时 + 重试上限）；beat 每分钟扫描到期主题批量入队
**验收要点:** worker 独立容器同一镜像；任务完成后推进 next_run_at；beat 用 Redis 分布式锁防重；失败任务有死信记录与告警日志
**Commit:** `feat(tasks): Celery 管道任务与定时调度`
**学习文档建议:** `07-Celery 任务幂等与重试语义`

### Task 3.2 Feed API 与增量读取

**范围：** `api/v1/` Feed 路由、`services/` 条目查询扩展、集成测试
**Interfaces:** `GET /api/v1/topics/{id}/items?cursor=&min_score=`（keyset 分页，禁止 offset 深翻页；默认仅 accepted 可见）
**验收要点:** 分页查询走索引（测试断言查询计划/查询数）；跨用户访问他人主题 → 404（不泄露存在性）
**Commit:** `feat(api): Feed 增量分页读取`

### Task 3.3 邮件推送闭环

**范围：** `push/` 渠道协议、邮件渠道与模板（汇总邮件 + 退订链接）、`models/` push_log、`tasks/` 推送任务、`services/` 推送服务与退订、单元 + 集成测试
**Interfaces:** `PushChannel.send(payload) -> PushReceipt`；`PushService.send_digest(topic, items) -> None`（渲染 → 入 `push` 队列 → 记 push_log）；退订端点 `POST /api/v1/topics/{id}/mute`
**验收要点:** 邮件发送 mock 化单测；重试 3 次指数退避仍失败 → push_log 记 failed 可查询；模板含退订链接与来源标注；集成测试断言"管道跑完 → 任务入队 → push_log 落库"全链路
**Commit:** `feat(push): 邮件汇总推送与退订`

### Task 3.4 配额、计量与可观测补全

**范围：** `services/` 配额服务、LLM 用量记录模型、健康检查增强（暴露队列积压）
**验收要点:** 每用户 LLM token/成本可按日聚合查询（内部接口即可）；配额扣减幂等（任务重试不重复扣）；`/readyz` 报告队列积压数
**Commit:** `feat(quota): 配额扣减与 LLM 成本计量`

---

## Phase 4：对话研究 Agent（对应里程碑 M4）

**交付判据**：API 层面一次提问返回 SSE 流式回答，结论带编号引用，工具轨迹与引用持久化。

### Task 4.1 会话与消息模型

**范围：** `models/` 会话与消息、迁移、`api/v1/` 会话 CRUD、集成测试
**Produces:** `Conversation`/`Message`（role enum user|assistant|tool；citations JSONB；tool_trace JSONB）
**Commit:** `feat(models): 会话与消息`

### Task 4.2 SSE 对话端点与工具循环集成

**范围：** `services/` 对话服务、`api/v1/` 流式端点、Retriever 复用为对话工具循环、集成测试
**Interfaces:** `POST /api/v1/conversations/{id}/messages` → `text/event-stream`；`ChatService.respond(conversation, user_msg) -> AsyncIterator[SSEEvent]`（事件序：`citations` 先行 → `delta`* → `done`）；工具集：web_search / fetch_page / 各源 search；单轮工具调用次数与总时长上限走配置，超限声明局限作答
**验收要点:** mock LLM 流式输出，断言事件顺序与 citations 落库；客户端断连（CancelledError）→ 计量与落库仍完整（不丢引用）；每用户并发对话数限流
**Commit:** `feat(chat): SSE 对话研究 Agent`
**学习文档建议:** `08-SSE 流式与断连处理`、`09-带引用的回答生成`

---

## Phase 5：前端与正式上线（对应里程碑 M5）

**交付判据**：三个界面可用、真实用户可注册订阅并收到邮件、监控告警就位。

### Task 5.1 React 骨架与认证流

**范围：** `frontend/` Vite+TS+ESLint 骨架、shared api client（JWT 存储、401 统一处理）、auth 特性、路由与布局壳
**验收要点:** 注册/登录/登出全通；token 过期自动处理；本地代理直连 FastAPI
**Commit:** `feat(frontend): 骨架与认证流`

### Task 5.2 订阅与 Feed 界面

**范围：** `features/topics/`（创建含计划预览确认、列表、手动执行）、`features/feed/`（评分/摘要/推荐理由/原文链接卡片；cursor 无限滚动）
**验收要点:** 创建流程能展示并修改 Planner 预览；Feed 在移动端宽度可用
**Commit:** `feat(frontend): 主题与 Feed 界面`

### Task 5.3 对话界面

**范围：** `features/chat/`（SSE 消费、打字机渲染、引用编号悬浮显示原文链接、断线重连提示、历史会话回看）
**验收要点:** 流式中断显示可重试状态；引用可点击新标签跳原文；历史会话完整回看
**Commit:** `feat(frontend): 对话界面`

### Task 5.4 上线验收与文档收尾

**范围：** deploy 完善、README 更新（在线 demo、截图）、Sentry 前后端接入、告警规则（队列积压/错误率/成本）
**验收清单（逐项勾选）:** 域名 HTTPS ✅ 注册→订阅→自动执行→收邮件 全链路真实走通 ✅ Sentry 收到测试错误 ✅ 队列/成本告警触发一次演练 ✅ Lighthouse 移动端分数记录 ✅ 全部 study 文档与文档同步检查（AGENTS.md 第 9 节）✅
**Commit:** `chore: 上线验收与文档收尾`

---

## 里程碑与 Phase 对照

| Phase | 里程碑 | 判据 | 预估（业余时间） |
|---|---|---|---|
| 1 | M1 骨架上线 | 全栈可部署、注册登录可用 | 3-5 天 |
| 2 | M2 Agent 管道 | 手动触发出条目 | 1-1.5 周 |
| 3 | M3 订阅闭环 | 自动执行+Feed+邮件 | 1 周 |
| 4 | M4 对话 Agent | SSE 带引用回答 | 1 周 |
| 5 | M5 前端上线 | 三界面+验收清单全绿 | 1-1.5 周 |

**执行方式**：按 Phase 顺序执行；Phase 内 Task 有依赖的按编号顺序（如 2.3 依赖 2.2），无依赖的（如 2.5 与 2.6）可并行。每 Phase 结束做一次"部署验收 + study 文档回顾"再进下一 Phase。

---

## 实施记录(与原计划的偏差修正)

> 依据 AGENTS.md 第 9 节:每 Phase 结束核对计划与实际交付,不一致处以本节记录。

**Phase 1(2026-09-06 完成,commit c0f0cb0…11b4371)**

- Task 1.6/1.7 的部署验收(真实域名 HTTPS、README 在线地址)因基础设施未就绪暂缓:部署流水线已改为手动触发(`workflow_dispatch`),上线前恢复 push 触发即可。
- Task 1.1 追加 `.dockerignore` 与 `.gitignore` 的 `.env.example` 例外(工具链完整性)。

**Phase 2(2026-09-06 完成,commit 4c59b10…4fa9027)**

- Task 2.5 通用抓取采用标准库 HTMLParser 提取正文,不引入 trafilatura 等重依赖(依赖纪律);提取精度由 Analyst 截断与评分兜底。
- Task 2.7 `POST /topics/{id}/run` 的"受配额限制"细化为:创建侧配额(quota_topics_max)已在本期落地;运行级配额依赖用量记录,随 Task 3.4 配额服务落地。
- 接口签名微调(已同步 architecture.md 第 5 节):`SourceClient.search`/`Retriever.collect` 增加 `topic_id` 参数(指纹计算需要);`Retriever.collect` 返回 `CollectResult(items, degraded)` 以携带单源降级清单;`StructuredRunner.run`/`ToolLoop.__init__` 增加 model 档位与上下文截断参数。
- 新增配置(已同步 .env.example):`TRADEWINDS_PIPELINE_SCORE_THRESHOLD`(暂定 6 分,Editor 准入下限)、`TRADEWINDS_GITHUB_TOKEN`(可选)、`TRADEWINDS_LOOP_*` 三项工具循环护栏。
- 集成测试访问数据库断言时使用独立 engine(asyncpg 连接绑定事件循环),不复用应用 lifespan 的 engine。

**Phase 3(2026-09-06 完成,commit 833d521…744cf78)**

- Task 3.1 worker/beat 不经 celery CLI 启动,改用自有入口模块(`python -m tradewinds.tasks.worker|beat`):Celery 应用模块导入零环境依赖,broker 由 `configure_broker` 注入,保证单元测试可安全 import。
- Task 3.3 推送范围:仅汇总邮件(digest);阈值即时推送与聚类抑制按 design.md 第 10 节仍不在一期范围。SMTP 未配置时投递结果记 skipped(email_disabled),不视为失败。推送任务重试仅覆盖"意外异常",渠道明确失败直接落 push_log failed 可查询,指数退避重试 3 次语义保留在 send_push 任务。
- Task 3.3 推送触发点在 PipelineService(可注入,手动 run 与调度 run 行为一致);入队分发回调由组合方注入,lifespan 负责 configure_broker,服务层不反向依赖任务模块。
- Task 3.4 配额扣减的幂等由"用量在 LLM 调用成功后记录一次 + 管道指纹去重"共同保证,未引入独立扣减表;`GET /usage/daily` 即计划中"内部接口"的最小实现。

**Phase 4(2026-09-06 完成,commit 710227e…14f3101)**

- Task 4.2 工具集当前为 search_arxiv / search_hackernews / search_github / fetch_page;计划中的 web_search 通用网页搜索因无免费稳定的搜索 API 客户端(Task 2.5 未含 websearch 源)暂缓,补齐后只需在 build_chat_registry 增加一个适配器。
- 流式实现为"循环完成后 citations→delta→done"的分帧输出(ToolLoop 走 complete 而非 stream),未做循环中途的 token 级流式;断连保护由此简化为"持久化先于流式输出 + shield 后台任务",验收语义(断连不丢引用与计量)已满足。真正 token 级流式需 ToolLoop 支持 provider.stream 的工具循环变体,记入 Phase 5 后优化项。
- 每用户并发对话限流为单 api 容器进程内实现(UserConcurrencyLimiter);多副本部署需改 Redis 计数,随扩展计划处理。

**Phase 5(2026-09-06 完成,commit cd1f388…)**

- Task 5.1/5.2/5.3 代码完成,验证方式为 `npm run lint` + `tsc --noEmit` + `vite build` 全绿与 CI frontend job;真实浏览器端到端(注册→订阅→自动执行→收邮件)属于 Task 5.4 上线验收清单,待基础设施就绪后执行。
- Task 5.4 上线验收清单(Sentry、告警演练、Lighthouse、在线地址回写 README)依赖 VPS/域名/Secrets,暂缓;部署流水线保持手动触发。
- 主题计划预览的"修改"通过编辑描述/频率触发 Planner 重编译实现(API 不支持直接改 plan 字段,与后端契约一致)。
- 前端 SSE 消费用 fetch 流式读取手动解析(POST + Authorization 头,EventSource 不适用);Feed 无限滚动配合后端 keyset 游标。

**扩展计划执行(2026-09-06,commit f56bd10 起)**

- 按扩展计划第一原则"由指标触发演进",仅执行阶段 0 必做件(纯代码部分)与 Agent 能力演进第一迭代(周期报告);阶段 1+(拆库/多实例/Prometheus/LLM 网关等)触发信号均未出现,明确不执行,待指标触发。
- 阶段 0 必做件:Sentry 可选接入(api/worker/beat/前端,DSN 未配置零开销)、`GET /ops/summary` 指标出口(X-Ops-Token)、备份/恢复脚本与 runbook(告警阈值见 docs/runbook.md);备份异地归档与恢复演练需部署后执行。
- 周期报告迭代(扩展计划 §3 第一项):Report 模型(0006 迁移,主题×周期唯一)、ReportService 幂等 upsert(条目按 created_at 落周期桶,每次 run 重算当期)、管道 run 后自动聚合、报告列表/详情/分享 API 与公开分享页(前端 /share/reports/:token)。
- 周期报告的邮件推送(设计文档"频率到期时聚合并邮件推送")暂未接线:推送通道与退订已就绪,待 SMTP 配置上线后接入 send_push 任务(与汇总邮件共用 push 队列与 push_log)。

**主动推送完善第一刀(2026-09-06,扩展计划 §3 + design.md §7)**

- 即时推送落地:accepted 条目评分 >= `TRADEWINDS_PUSH_IMMEDIATE_THRESHOLD`(默认 8)→ 单条即时邮件,push_log 记 push_type=immediate;design.md §7 暂定阈值已回写为配置项并去掉"暂定"。
- 抑制规则:同聚类(cluster_key)24h 内(窗口可配)已有待发/已发即时推送 → 跳过;单条以 digest_key=`item:<id>` 去重,重跑不重推。
- 投递复用既有链路:入 push 队列、send_push 重试语义、SMTP 未配置记 skipped 均不变。
- 扩展计划 §3 其余项(跨会话记忆/自定义 RSS/RAG 已读内容/阈值动态化)依赖数据积累或向量库,按价值顺序后续迭代。

**自定义 RSS 源(2026-09-06,扩展计划 §3)**

- RssClient(RSS 2.0 / Atom 双格式,标准库解析)作为第四类 SourceClient;feed_sources 表(0008 迁移,主题+URL 唯一)挂在主题上,创建即健康校验(不可解析 → 422 invalid_feed),beat 每日复检更新 healthy/broken。
- 管道检索:自定义源始终参与抓取(用户显式添加即意图,不经 Planner 源选择);Retriever.collect 增 extra_clients 参数,broken 源照常抓取并由单源降级机制标注。
- 投递/评分/去重全部复用既有管道;tools/base 抽出 Limiter 协议解耦请求助手与限速器实现。

**跨会话记忆第一刀(2026-09-06,扩展计划 §3 第一项)**

- 行为信号:item_clicks 表(0009 迁移,用户×条目唯一)记录 Feed 点击;POST /items/{id}/click 幂等,归属隔离 404;前端 Feed 卡片点击 fire-and-forget 上报。
- 偏好画像:build_profile 聚合"点击条目的聚类键(强信号)+ 其他主题关键词(弱信号)",去重限量 12 条;注入 Analyst 评分 prompt 的"用户历史偏好"段落,并显式声明"仅作参考信号,判定仍以本主题标准为准"——记忆影响取舍,不劫持判定。
- 管道与 Analyst 契约微调:Analyst.score 增 preferences 关键字参数;PipelineService 增 preference_builder 注入点;未注入时行为与旧版一致。
- 阈值动态化(§3)待 push_log/点击数据积累后做自适应;RAG 已读检索待 pgvector 迭代。

**扩展计划收尾(2026-09-06,commit f60f6e7…a37a7e7)**

- 评测体系常态化:Analyst 8 例 + Editor 6 例金标集落地,三角色齐备;断言业务要点(分数区间/聚类一致/核心实体保留/反脑补),CI 必跑即 prompt 回归门禁;线上抽样人工标注非代码项,待运营数据。
- 阈值动态化:effective_immediate_threshold 按主题近期评分中位数在全局阈值 ±1.0 内自适应,冷启动(<10 条)用全局值;高分主题抬门槛避免刷屏,低分主题浮出精华;集成测试验证高分历史抑制 8.5 分条目。
- RAG 已读内容检索:pgvector 方案(扩展计划明确不引入独立向量库);0010 迁移启用 vector 扩展(向量列不锁维度,ANN 索引留待规模触发);管道 run 后对 accepted 条目生成嵌入(upsert,失败降级);GET /items/search 与对话工具 search_history 限定本人条目;总开关 TRADEWINDS_EMBEDDING_MODEL 默认关闭。compose/CI postgres 切换 pgvector/pgvector:pg16。
- web_search 通用搜索工具维持暂缓(无免费稳定搜索 API)。

**演示就绪(2026-09-06,项目定位调整后)**

> 项目定位调整为面试可演示的作品集项目(design.md v0.3),原"待上线"项转为演示等价物,实施见 [2026-09-06-demo-readiness-plan.md](2026-09-06-demo-readiness-plan.md)。

- Task 5.4 上线验收清单(域名 HTTPS、Sentry 演练、Lighthouse、在线地址)随定位调整移除(N6),不做。
- 周期报告邮件推送接线完成(原"待 SMTP 配置"项):PushType 增 report、PushService.prepare_report(digest_key=report:<id> 幂等)、管道报告 upsert 后推送;无迁移(native_enum=False)。
- Mailpit 演示邮箱接入 compose(api/worker 演示 SMTP 由 environment 注入,优先级高于 .env);顺带清理死配置 TRADEWINDS_EMAIL_ENABLED(定义后从未被消费,邮件开关实为 SMTP host/sender 是否为空)。
- 演示数据 seed:`tradewinds/demo_seed.py`(演示账号/主题/条目/报告/会话/点击/推送历史,幂等),`make seed`。
- 前端静态托管:api 容器经 `mount_spa` 托管构建产物(TRADEWINDS_STATIC_DIR,Dockerfile 增 node 构建阶段);`make demo` 一键起全栈+迁移+seed。
- 本机无 Docker:compose/集成链路未实跑,单测(190)与 lint/mypy 全绿,集成测试与 make demo 走查待 CI 或有 Docker 环境。

**集成测试首次真实执行暴露的问题修复(2026-09-06,CI run #47-#50)**

- 背景:integration job 此前被 Settings 缺配置/依赖下载超时挡在早期阶段,套件从未真正执行;首次跑通后逐轮暴露历史漂移与真实 bug,共四轮收敛(19 失败→12→最终全绿)。
- 生产 bug:①openai 3.x 的 parse 不再接受 response_model,结构化输出(Planner/Analyst/Editor)整体失效,改 response_format + message.parsed;②Feed keyset 游标取 rows[limit](下一页首条)导致每页边界丢一条,改 rows[limit-1];③报告列表 item_count 为计算字段,from_attributes 直灌必 500,改显式构造;④SSE 会话归属校验在流开始后抛 404 无法回写状态码,前置到端点;⑤偏好画像 SELECT DISTINCT+ORDER BY 不符合 PG 约束,改 GROUP BY。
- 测试修复:假件对齐 role/user_id 接口与 seen_hashes 增量语义;test_feed 漏替换 Planner;test_chat 假件 tier 用字符串、SSE 解析未按信封格式取 data;test_immediate_push 评分传字符串、自适应断言与夹具评分不符;test_push 断言未包含 report/immediate 推送类型;test_migrations 的 async 测试与 alembic 内部 asyncio.run 冲突,且 downgrade 会清空共享库,改为一次性独立数据库。
- 推送投递机制认知:celery 的 send_task 不受 task_always_eager 影响,集成测试改为覆盖 app.state.push_dispatch 直接同步执行任务函数。
