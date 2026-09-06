# TradeWinds MVP 实施计划书

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付可真实运营的 TradeWinds MVP——主题订阅检索管道、Feed、邮件推送、对话研究 Agent 与 React 前端，单 VPS 上线。

**Architecture:** FastAPI（api/worker/beat 三容器）+ PostgreSQL + Redis + Celery + 自研 Agent 编排层（工具循环/结构化输出/流式）+ React SPA。运行时与包结构见 [architecture.md](../architecture.md)。

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2.0 async · Alembic · Celery · Redis · httpx · OpenAI-compatible SDK · React/Vite/TS · Docker Compose · Caddy

**Spec:** [docs/design.md](../design.md) v0.2 —— 本计划从 spec 出发，执行者两份都要读。

**计划约定：** 本计划锁定**接口契约、文件落点、验收标准**；每个 Task 内部的具体实现代码在执行时按 TDD 展开（先写测试看它失败，再实现让它通过）——这是有意为之，与 AGENTS.md "表和代码细节由开发时设计"一致。Task 内步骤模板固定为：

```
1. 写失败测试（契约来自本文 Interfaces 列）
2. 跑测试确认失败 → 3. 最小实现 → 4. 跑测试通过 → 5. lint + mypy 通过
6. 写 docs/study/ 学习文档（AGENTS.md 第 10 节格式）→ 7. Commit
```

下文各 Task 只列差异信息（文件、接口、验收要点、特殊步骤），不重复模板。

## Global Constraints（每个 Task 隐含遵守）

- Python 3.13，src layout（`src/tradewinds/`）；依赖方向与命名规范见 architecture.md 第 2/4 节，违反即返工
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

**Files:** `pyproject.toml`（ruff/mypy/pytest/coverage 配置）、`Makefile`、`.env.example`、`.pre-commit-config.yaml`、`.github/workflows/ci.yml`、`src/tradewinds/__init__.py`、`src/tradewinds/main.py`（`create_app()` 工厂，先只挂 `/healthz`）、`tests/unit/test_app.py`
**Produces:** `create_app() -> FastAPI`（后续所有路由经此挂载）；Makefile 目标 `lint/type/test/dev`
**验收要点:** `ruff check`、`mypy src`、`pytest` 三条命令零错误零通过性失败；CI 在 PR 上跑同样三条 + 集成测试 job（起 postgres/redis service）；pre-commit 安装成功
**Commit:** `chore: 工程骨架与工具链`

### Task 1.2 核心配置与结构化日志

**Files:** `src/tradewinds/core/config.py`、`core/logging.py`、`core/exceptions.py`、`tests/unit/core/test_config.py`
**Produces:** `get_settings() -> Settings`（缓存单例；字段含 `database_url`、`redis_url`、`jwt_secret`、`jwt_expire_minutes`、`model_low`、`model_mid`、`llm_api_base`、`llm_api_key`、`quota_topics_max: int = 5`）；`setup_logging()` structlog JSON 配置；`TradeWindsError(msg, code)` 异常基类与 `NotFoundError`/`AuthError`/`QuotaExceededError`
**验收要点:** 缺必填配置时 `get_settings()` 在 import 期 fail-fast 抛出明确错误；`Settings` 新增字段全部有注释并同步 `.env.example`；异常子类携带稳定错误码
**Commit:** `feat(core): 配置、结构化日志与异常基类`

### Task 1.3 数据库基线与 users 表

**Files:** `core/db.py`、`models/base.py`（时间戳/主键 mixin）、`models/user.py`、`alembic/`（init + env 配置为 async）、首个迁移、`tests/integration/test_migrations.py`
**Produces:** `async_session_factory`；`User` 模型（email 唯一、password_hash、notify_email、quota_topic_max、created_at）；alembic 命令在真库 up/down 通过
**验收要点:** 集成测试用 `docker compose` 的 PG（或 testcontainers）跑 `alembic upgrade head` 断言表结构；模型表名为复数
**Commit:** `feat(models): 数据库基线与 users 表`

### Task 1.4 注册登录（JWT）

**Files:** `core/security.py`、`services/auth_service.py`、`api/deps.py`（`get_db`/`get_current_user`）、`api/v1/auth.py`、`tests/unit/services/test_auth_service.py`、`tests/integration/test_auth_api.py`
**Interfaces (Produces):** `AuthService.register(email, password) -> User`（邮箱重复抛 `AuthError(409)`）；`AuthService.login(email, password) -> TokenPair`；`get_current_user` 依赖（无效/过期 JWT → 401 统一错误体 `{code, message}`）
**验收要点:** bcrypt 哈希不可逆查；密码强度最低 8 位；登录失败统一 401 不区分"用户不存在/密码错"；集成测试覆盖 注册→登录→带 token 访问受保护端点→篡改 token 401
**Commit:** `feat(auth): 注册登录与 JWT`

### Task 1.5 Redis 接入与 IP 限流

**Files:** `core/redis.py`、`services/rate_limit_service.py`、`api/deps.py` 增 `get_redis`、`tests/unit/services/test_rate_limit_service.py`、`tests/integration/test_rate_limit.py`
**Interfaces (Produces):** `RateLimitService.check(key: str, limit: int, window_seconds: int) -> bool`（Redis INCR+EXPIRE 实现，原子）
**验收要点:** 注册/登录路由按 IP 限流（窗口 60s / 10 次，值走配置）；Redis 不可用时**放行并告警日志**（限流是保护，不因它停服）；集成测试用 fakeredis 或真 Redis
**Commit:** `feat(core): Redis 接入与 IP 限流`

### Task 1.6 Docker Compose 与 HTTPS 部署

**Files:** `docker-compose.yml`（api/postgres/redis/caddy 四服务 + 健康检查 + depends_on 条件）、`deploy/Caddyfile`、`deploy/prod.compose.yml`、`api` 的 `Dockerfile`（多阶段：builder + slim 运行时，非 root 用户）
**验收要点:** 本地 `make up` 一条命令起全栈；`/healthz`（进程存活）与 `/readyz`（DB+Redis 连通）语义分离；生产 compose 中 api 与数据库同机但独立容器
**Commit:** `chore(deploy): Compose 全栈与 Caddy HTTPS`

### Task 1.7 CI/CD 与首次上线

**Files:** `.github/workflows/deploy.yml`（main 合并 → build/push 镜像 → SSH 执行 `docker compose pull && up -d && alembic upgrade head`）
**验收要点:** 部署脚本的每一步失败都会中断且不破坏旧版本（先 pull 后切换）；上线后真实域名 HTTPS 可访问，README 增加在线地址
**Commit:** `ci: 构建与部署流水线，空壳上线`
**学习文档建议:** `01-工程骨架：pyproject 统一配置`、`02-JWT 在无状态 API 中的使用`

---

## Phase 2：Agent 管道核心（对应里程碑 M2）

**交付判据**：创建主题后手动触发，数据库出现带评分、摘要、原文链接的条目；单源故障不影响出报。本期全部离线可测（mock LLM + 录制固件）。

### Task 2.1 topics 与 items 表

**Files:** `models/topic.py`、`models/item.py`、迁移、`tests/integration/test_topic_models.py`
**Produces:** `Topic`（name/description/plan JSONB/cadence enum daily|weekly/status/last_run_at/next_run_at）、`Item`（source/url/url_hash 唯一约束/title/raw_content/published_at/score/cluster_key/summary/reason/status enum pending→scored→accepted|rejected）——字段在迁移设计时定稿，此处为契约语义
**验收要点:** url_hash 主题内唯一；`topics(next_run_at)` 支持到期扫描查询；缩略内容截断有统一工具函数
**Commit:** `feat(models): 主题与条目模型`

### Task 2.2 编排层：LLMProvider 与计量

**Files:** `agents/orchestrator/llm.py`、`agents/orchestrator/metering.py`、`tests/unit/agents/test_llm_provider.py`
**Interfaces:** 见 architecture.md 第 5 节 `LLMProvider`；`MeteringRecorder.record(user_id, role, tier, usage) -> None`（写结构化日志，Phase 3 起落库）
**验收要点:** 基于 OpenAI-compatible SDK 的实现，base_url/model 全部来自 Settings；429/5xx 指数退避重试（上限 3 次）；`response_model` 路径返回经校验的 `LLMResult[T]`（含 usage）；测试全部 mock SDK
**Commit:** `feat(agents): LLMProvider 抽象与计量`

### Task 2.3 编排层：结构化输出执行器与工具循环

**Files:** `agents/orchestrator/structured.py`、`agents/orchestrator/loop.py`、`agents/orchestrator/streaming.py`、`tests/unit/agents/test_structured.py`、`test_loop.py`、`test_streaming.py`
**Interfaces:** `StructuredRunner.run(prompt, response_model) -> T`（校验失败把校验错误回注重试，上限 2 次）；`ToolLoop.run(messages) -> LoopResult`（见 architecture.md 第 5 节；工具失败作为工具结果回注模型而非中断；`max_iterations=10`、`total_timeout=120s` 走配置）；`SSEEvent` 封装（delta/citations/done/error 四类事件）
**验收要点（自研三风险，必须各有测试）:** ①上下文超长按"保系统指令+最近工具结果"截断 ②工具抛异常 → 模型收到错误描述并继续循环 ③SSE 生成器中途抛错 → 客户端收到 error 事件而非连接静默断开
**Commit:** `feat(agents): 结构化输出执行器与工具循环`
**学习文档建议:** `03-自研 Agent 工具循环`、`04-结构化输出校验重试`

### Task 2.4 Planner：主题编译

**Files:** `agents/schemas/plan.py`（`RetrievalPlan`）、`agents/prompts/planner.md`、`agents/planner.py`、`tests/agents/test_planner_golden.py`、`tests/agents/golden/`
**Interfaces:** `Planner.compile(description: str, cadence) -> RetrievalPlan`（字段：keywords、sources、arxiv_categories、github 查询参数、window_days、relevance_criteria——对齐 design.md 4.2 示例）
**Produces（金标集机制，后续长期用）:** `tests/agents/golden/` 下 ≥10 个"描述→计划要点"用例；测试断言关键字覆盖与源选择，不逐字比对
**验收要点:** prompt 独立文件加载；schema 校验失败自动重试（复用 2.3）；金标集测试 CI 必跑
**Commit:** `feat(agents): Planner 主题编译与金标集`

### Task 2.5 信息源客户端（arXiv / HN / GitHub / fetcher）

**Files:** `tools/base.py`、`tools/arxiv.py`、`tools/hackernews.py`、`tools/github.py`、`tools/fetcher.py`、`tests/contract/test_arxiv.py`、`test_hackernews.py`、`test_github.py`、`tests/contract/fixtures/`
**Interfaces:** 见 architecture.md 第 5 节 `SourceClient`；`CandidateItem`（source/url/title/published_at/raw_content）；`Fetcher.fetch(url) -> ExtractedContent`（httpx + 正文提取库）
**验收要点:** 每个源 ≥3 条录制固件的契约测试（正常/空结果/畸形响应）；遵守各源速率限制（客户端内置信号量 + 请求间隔）；`search` 内部调用 `seen_hashes` 过滤已见 URL（指纹算法在 `tools/base.py`，sha256(normalized_url)+topic_id）
**Commit:** `feat(tools): 三个信息源客户端与网页抓取`
**学习文档建议:** `05-异步并发抓取与速率控制`

### Task 2.6 Retriever 与 Analyst

**Files:** `agents/retriever.py`、`agents/analyst.py`、`agents/prompts/analyst.md`、`agents/schemas/score.py`、`tests/agents/test_retriever.py`、`test_analyst.py`
**Interfaces:** `Retriever.collect(plan, seen_hashes) -> list[CandidateItem]`（asyncio.gather 并发各源；单源异常记 warning 并在结果上标注降级，不上抛）；`Analyst.score(items, topic) -> list[ScoredItem]`（0-10 分 + 聚类键；低价位模型、raw_content 先截断）
**验收要点:** mock 一个源抛异常 → 其余源条目正常产出且带降级标记；评分低于阈值的条目状态置 rejected 不进 Editor
**Commit:** `feat(agents): Retriever 并发检索与 Analyst 评分聚类`

### Task 2.7 Editor 单条摘要与管道集成

**Files:** `agents/editor.py`、`agents/prompts/editor.md`、`services/item_service.py`、`services/pipeline_service.py`、`services/topic_service.py`、`api/v1/topics.py`、`tests/integration/test_pipeline.py`
**Interfaces:** `Editor.summarize(item, topic) -> ItemDigest`（summary + reason）；`PipelineService.run_topic(topic) -> PipelineResult`（编排 Retriever→Analyst→Editor→落库全流程，返回各阶段计数）；REST：`POST /api/v1/topics`（含 Planner 计划预览返回）、`GET/PATCH/DELETE /topics/{id}`、`POST /topics/{id}/run`（同步触发管道，受配额限制）
**验收要点:** 集成测试：建主题（mock Planner）→ run（mock 全部源与 LLM）→ 断言 items 落库、状态流转正确、重复 run 不产生重复条目；配额满抛 `QuotaExceededError(402/429)`
**Commit:** `feat(pipeline): 订阅检索管道与主题 API`
**学习文档建议:** `06-多 Agent 管道的降级设计`

---

## Phase 3：订阅闭环（对应里程碑 M3）

**交付判据**：主题按频率自动执行，Feed 可分页读取，邮箱收到汇总邮件；队列可观测。

### Task 3.1 Celery 接入与定时调度

**Files:** `tasks/celery_app.py`、`tasks/pipeline_tasks.py`、`tasks/schedules.py`、`docker-compose.yml`（增 worker/beat 容器）、`tests/integration/test_tasks.py`
**Interfaces:** `run_topic_task(topic_id) -> dict`（任务名 `tradewinds.tasks.pipeline_tasks.run_topic`，入 `pipeline` 队列；acks_late + 任务级超时 + 重试上限）；beat 每分钟扫描到期主题批量入队
**验收要点:** worker 是独立容器同一镜像；任务把 next_run_at 推进到下周期；beat 用分布式锁防重（Redis 锁）；失败任务进死信记录并有告警日志
**Commit:** `feat(tasks): Celery 管道任务与定时调度`
**学习文档建议:** `07-Celery 任务幂等与重试语义`

### Task 3.2 Feed API 与增量读取

**Files:** `api/v1/items.py`、`services/item_service.py` 扩展、`tests/integration/test_feed_api.py`
**Interfaces:** `GET /api/v1/topics/{id}/items?cursor=&min_score=`（keyset 分页，禁止 offset 深翻页；仅 accepted 状态默认可见）
**验收要点:** 100 条数据下分页查询走索引（测试断言查询数）；跨用户访问他人主题 → 404（不泄露存在性）
**Commit:** `feat(api): Feed 增量分页读取`

### Task 3.3 邮件推送闭环

**Files:** `push/base.py`、`push/email.py`、`push/templates/`（Jinja2：汇总邮件 + 退订链接）、`models/push_log.py`、`tasks/push_tasks.py`、`services/push_service.py`、`tests/unit/push/test_email.py`、`tests/integration/test_push_flow.py`
**Interfaces:** `PushChannel.send(payload) -> PushReceipt`；`PushService.send_digest(topic, items) -> None`（渲染模板 → 入 `push` 队列 → 记 push_log）；退订端点 `POST /api/v1/topics/{id}/mute`
**验收要点:** 邮件发送 mock 化单测；重试 3 次指数退避后仍失败 → push_log 记 failed 且可查询；模板含退订链接与来源标注；集成测试断言"管道跑完 → 任务入队 → push_log 落库"全链路
**Commit:** `feat(push): 邮件汇总推送与退订`

### Task 3.4 配额、计量与可观测补全

**Files:** `services/quota_service.py` 扩展、`models/` 增 LLM 用量记录表、`api/v1/health.py` 增强（队列长度暴露）、structlog 字段规范落文档
**验收要点:** 每用户 LLM token/成本可按日聚合查询（内部接口即可）；`/readyz` 报告队列积压数；配额扣减幂等（任务重试不重复扣）
**Commit:** `feat(quota): 配额扣减与 LLM 成本计量`

---

## Phase 4：对话研究 Agent（对应里程碑 M4）

**交付判据**：前端外的 API 层面，一次提问返回 SSE 流式回答，结论带编号引用，工具轨迹与引用持久化。

### Task 4.1 会话与消息模型

**Files:** `models/conversation.py`、迁移、`api/v1/conversations.py`（CRUD）、`tests/integration/test_conversations.py`
**Produces:** `Conversation`/`Message`（role enum user|assistant|tool；citations JSONB；tool_trace JSONB）
**Commit:** `feat(models): 会话与消息`

### Task 4.2 SSE 对话端点与工具循环集成

**Files:** `services/chat_service.py`、`api/v1/conversations.py` 增流式端点、`agents/retriever.py` 复用为对话工具循环、`tests/integration/test_chat_sse.py`
**Interfaces:** `POST /api/v1/conversations/{id}/messages` → `text/event-stream`；`ChatService.respond(conversation, user_msg) -> AsyncIterator[SSEEvent]`（事件序：`citations` 先行 → `delta`* → `done`）；工具集：web_search/fetch_page/各源 search；单轮工具调用与总时长上限走配置，超限声明局限作答
**验收要点:** 测试 mock LLM 流式输出，断言事件顺序与 citations 落库；客户端断连（CancelledError）→ 计量与落库仍完整（不丢引用）；每用户并发对话数限流
**Commit:** `feat(chat): SSE 对话研究 Agent`
**学习文档建议:** `08-SSE 流式与断连处理`、`09-带引用的回答生成`

---

## Phase 5：前端与正式上线（对应里程碑 M5）

**交付判据**：三个界面可用、真实用户可注册订阅并收到邮件、监控告警就位。

### Task 5.1 React 骨架与认证流

**Files:** `frontend/`（Vite+TS+ESLint）、`shared/api/`（fetch 封装 + JWT 存储 + 401 统一跳转）、`features/auth/`、路由与布局壳
**验收要点:** 注册/登录/登出全通；token 过期自动处理；代理配置本地直连 FastAPI
**Commit:** `feat(frontend): 骨架与认证流`

### Task 5.2 订阅与 Feed 界面

**Files:** `features/topics/`（创建含计划预览确认、列表、手动执行按钮）、`features/feed/`（条目卡片：评分/摘要/推荐理由/原文链接；cursor 分页无限滚动）
**验收要点:** 创建流程能展示并修改 Planner 预览；Feed 在移动端宽度可用
**Commit:** `feat(frontend): 主题与 Feed 界面`

### Task 5.3 对话界面

**Files:** `features/chat/`（SSE 消费：EventSource/fetch 流、打字机渲染、引用编号悬浮显示原文链接、断线重连提示）
**验收要点:** 流式中断显示可重试状态；引用可点击跳转原文（新标签）；历史会话列表与回看
**Commit:** `feat(frontend): 对话界面`

### Task 5.4 上线验收与文档收尾

**Files:** `deploy/` 完善、`README.md` 更新（在线 demo、截图）、Sentry 接入（前后端）、告警规则（队列积压/错误率/成本）
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
