# TradeWinds 架构与项目结构

| | |
|---|---|
| 版本 | v0.1 |
| 日期 | 2026-09-06 |
| 状态 | 评审中 |
| 关联文档 | [设计文档](design.md) · [扩展计划](scaling-plan.md) · [实施计划](plans/) |

> 设计文档约定"做什么、为什么"；本文约定"代码怎么组织"——运行时架构、包结构、命名与依赖规则。实现计划据此拆解任务。结构可随实现演进，但**依赖规则与命名规范不因图省事而破坏**。

## 1. 运行时架构

```mermaid
flowchart TB
    subgraph Client["客户端"]
        SPA["React SPA"]
        Mail["用户邮箱"]
    end

    subgraph VPS["Docker Compose · 单 VPS"]
        Caddy["Caddy<br/>HTTPS 入口 / 反代 / 静态托管"]
        API["api 容器<br/>FastAPI · REST + SSE"]
        Worker["worker 容器 ×N<br/>Celery Worker"]
        Beat["beat 容器<br/>Celery Beat 调度"]
        PG[("PostgreSQL<br/>业务数据")]
        Redis[("Redis<br/>队列 · 缓存 · 限流")]
    end

    subgraph External["外部依赖"]
        LLM["DeepSeek 等<br/>LLM API"]
        SRC["信息源<br/>arXiv / HN / GitHub / Web 搜索"]
        SMTP["邮件发信服务"]
    end

    SPA -->|HTTPS REST/SSE| Caddy --> API
    API --> PG & Redis
    Beat -->|入队| Redis
    Redis -->|消费| Worker
    Worker --> PG & Redis
    API -->|对话研究（同步）| LLM
    Worker -->|管道任务| LLM
    Worker --> SRC
    Worker --> SMTP --> Mail
```

要点：

- **api 与 worker 职责分离**：同步请求（REST/SSE）在 api；一切可能耗时的处理（检索管道、邮件）走 Celery 任务在 worker 执行。对话研究是唯一在 api 进程内同步调用 LLM 的场景（用户正等待流式响应）
- **beat 是全局唯一调度者**：只负责"到点入队"，不执行任何业务逻辑
- 所有容器同镜像不同启动命令，CI 只构建一次

## 2. 模块依赖规则

```mermaid
flowchart TD
    API["api（路由层）"] --> SVC["services（业务逻辑）"]
    SVC --> AG["agents（编排层 + 四角色）"]
    SVC --> PUSH["push（推送渠道）"]
    AG --> ORCH["agents.orchestrator（自研编排层）"]
    AG --> TOOLS["tools（信息源客户端）"]
    SVC & AG & PUSH & TOOLS --> MODELS["models（DB 模型）"]
    SVC & AG & PUSH & TOOLS & API & MODELS --> CORE["core（配置/日志/安全/异常）"]
```

硬性规则（review 时逐条检查）：

1. 依赖方向只能自上而下，**禁止反向 import**（如 models 不得 import services）
2. `core` 不依赖任何业务模块
3. 路由层（api）不含业务逻辑：只做校验、调用 services、组装响应
4. `agents` 不直接 import `api` 的任何内容；`tools` 不 import `agents`（工具被编排层调用，反向依赖即错）
5. 跨层传递的数据一律为 Pydantic 模型，禁止裸 dict 在模块边界流动

## 3. 项目结构

**只约定到目录与职责这一层**。具体文件名与模块拆分在实现时按 AGENTS.md 第 6 节的拆分信号决定，本文不锁定任何 `.py` 文件名。

```
TradeWinds/
├── pyproject.toml / Makefile / .env.example   # 依赖与工具链配置、统一命令入口、环境变量样例
├── docker-compose.yml + deploy/               # 编排定义与生产配置（HTTPS 入口、生产覆写）
├── .github/workflows/                         # CI（lint + type + test）与部署流水线
├── docs/                                      # design / architecture / scaling-plan / plans/ / study/
├── src/tradewinds/
│   ├── api/            # 路由层：参数校验 + 调用 services + 组装响应，不含业务逻辑；版本化（v1/）
│   ├── services/       # 业务逻辑：路由薄、服务厚，一个领域一个模块
│   ├── agents/
│   │   ├── orchestrator/   # 自研编排层（LLM 抽象、工具循环、结构化输出、流式、计量），不含业务
│   │   ├── prompts/        # 全部 prompt 独立文件，代码不内嵌
│   │   ├── schemas/        # 角色间传递的 Pydantic 模型（检索计划、评分、摘要）
│   │   └── 四角色各一个模块 # planner / retriever / analyst / editor
│   ├── tools/          # 信息源客户端：base 协议 + arxiv / hn / github / websearch / 通用抓取
│   ├── tasks/          # Celery：应用工厂、任务定义、队列路由、beat 调度
│   ├── models/         # SQLAlchemy 模型，一个聚合一个模块
│   ├── push/           # 推送渠道：协议 + 邮件实现 + 模板
│   └── core/           # 配置、日志、安全、异常、DB/Redis 工厂；无业务语义
├── frontend/src/
│   ├── features/       # auth / topics / feed / chat，按业务特性组织，跨特性不互相 import
│   └── shared/         # api client、通用组件、类型
└── tests/              # unit / contract（录制固件）/ agents（金标集）/ integration，镜像 src 结构
```

## 4. 命名规范

| 对象 | 规范 | 示例 |
|---|---|---|
| 包/模块 | 小写下划线，单数名词，名即职责 | `item_service.py`，禁止 `utils.py`、`common.py` |
| 类 | 大驼峰 | `TopicService`、`ArxivClient` |
| 函数/变量 | 小写下划线，动词开头（函数） | `create_topic`、`fetch_since` |
| Pydantic 模型 | 后缀表用途：请求/响应/Agent 产物 | `TopicCreate`、`ItemRead`、`RetrievalPlan` |
| SQLAlchemy 模型 | 单数类名，**复数表名** | 类 `User` → 表 `users` |
| Celery 任务 | `tradewinds.tasks.<模块>.<动作>` 全限定名 | `tradewinds.tasks.pipeline_tasks.run_topic` |
| 队列 | 短小写，按重量命名 | `default`、`pipeline`、`push` |
| 环境变量 | `TRADEWINDS_` 前缀大写 | `TRADEWINDS_DATABASE_URL` |
| 数据库迁移 | 自动生成 + 语义化 message | `add topics table` |
| 分支 | `feat/`、`fix/`、`docs/` 前缀 | `feat/orchestrator-loop` |
| API 路径 | 复数资源、kebab 无、版本前缀 | `/api/v1/conversations/{id}/messages` |
| 测试文件 | `test_<被测模块名>.py`，镜像 src 路径 | `tests/unit/services/test_topic_service.py` |

## 5. 关键抽象（接口契约）

实现计划与编码以这些协议为锚点，签名变更须同步本文件：

```python
# agents/orchestrator/llm.py —— 模型供应商抽象，DeepSeek/GLM 可切换
class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], *, model: ModelTier,
                       response_model: type[T] | None = None) -> LLMResult[T]: ...
    def stream(self, messages: list[Message], *, model: ModelTier) -> AsyncIterator[str]: ...

# agents/orchestrator/loop.py —— 工具循环（Retriever 对话模式的核心）
class ToolLoop:
    def __init__(self, provider: LLMProvider, tools: ToolRegistry, *,
                 model: ModelTier = ModelTier.low,
                 max_iterations: int = 10, total_timeout: float = 120.0,
                 max_context_chars: int = 24_000): ...
    async def run(self, messages: list[Message]) -> LoopResult: ...

# agents/orchestrator/structured.py —— 结构化输出执行器
class StructuredRunner:
    async def run(self, prompt: str, response_model: type[T], *,
                  model: ModelTier) -> T: ...

# tools/base.py —— 所有信息源客户端同构，新增源=新增一个实现
class SourceClient(Protocol):
    name: str
    async def search(self, plan: RetrievalPlan, *,
                     seen_hashes: set[str]) -> list[CandidateItem]: ...

# push/base.py —— 推送渠道抽象（邮件先实现，站内通知后接）
class PushChannel(Protocol):
    async def send(self, payload: PushPayload) -> PushReceipt: ...
```

约定：`ModelTier`（low/mid）映射到具体供应商型号的配置在 `core/config.py`，代码中不出现型号字符串。

## 6. 工程配套（大项目必备清单）

| 项 | 落点 | 要求 |
|---|---|---|
| 代码风格 | ruff（format + lint），配置在 pyproject.toml | CI 强制 |
| 类型检查 | mypy strict（src 范围） | CI 强制 |
| 测试 | pytest + pytest-asyncio + coverage（目标：核心逻辑行覆盖 ≥ 85%） | CI 强制 |
| 提交钩子 | pre-commit（ruff、mypy 快速档） | 本地强制 |
| 统一入口 | Makefile：`lint` / `type` / `test` / `migrate` / `dev` / `up` / `down` | 禁止凭记忆敲长命令 |
| 环境变量 | `.env.example` 全量样例带注释；Settings 启动即校验，缺配 fail-fast | — |
| 数据库迁移 | Alembic，只进不退（回滚用新迁移），CI 起真库跑迁移 | — |
| 密钥管理 | 全部走环境变量；仓库内无任何真实密钥；Sentry/DSN 等同密钥管理 | — |
| 错误码 | `core/exceptions` 集中定义业务异常 → 统一错误响应体 `{code, message}` | — |
| 文档纪律 | 见 AGENTS.md 第 0/9/10 节（阅读地图、文档同步、study 学习文档） | 每个 Task 后写 study |
