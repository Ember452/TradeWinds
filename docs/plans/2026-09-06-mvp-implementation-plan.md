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
